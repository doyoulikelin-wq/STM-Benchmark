"""Offline-testable R07 gain codec and one-attempt bookkeeping support.

No CLI, connection, catalog mutation, authorization, claim creation or automatic
recovery. The root runner supplies its already-bound transport and atomic claim.
Full state, logger, freshness and finite exposure guards remain in that runner.
"""
import copy
import math
import struct
import types

MANUAL_SHA256 = 'f7133dbbca86524fb0ab63dc5c2d4e190aeecfd276d833ae35f67518a8465f7c'
MANUAL_PAGES = {'ZCtrl.GainSet': 70, 'ZCtrl.GainGet': 70, 'Scan.SpeedSet': 103}
ORIGINAL_GAIN = (3.4123519981887895e-12, 4.29563588113524e-05, 7.943764757101235e-08)
INDUCTION_GAIN = (3.4123519981887895e-12, 8.59127176227048e-05, 3.9718823785506174e-08)
GAIN_SCHEMA = {'inputs': ['f', 'f', 'f'], 'outputs': [], 'access': 'write'}
SPEED_SCHEMA = {'inputs': ['f', 'f', 'f', 'f', 'H', 'f'], 'outputs': [], 'access': 'write'}


def f32(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Finite numeric float32 required')
    return struct.unpack('>f', struct.pack('>f', value))[0]


def gain_tuple(values):
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError('Gain order is [P, T_seconds, I]')
    result = tuple(f32(v) for v in values)
    if not all(v > 0 for v in result) or result[2] != f32(result[0] / result[1]):
        raise ValueError('Positive consistent float32 P/T/I required')
    return result


def target_pair(mode):
    if mode == 'configure_induction':
        return ORIGINAL_GAIN, INDUCTION_GAIN
    if mode == 'restore_original':
        return INDUCTION_GAIN, ORIGINAL_GAIN
    raise ValueError('Only this finite R07 configure or restore pair')


def encode_gain_body(values):
    values = gain_tuple(values)
    if values not in (ORIGINAL_GAIN, INDUCTION_GAIN):
        raise ValueError('Gain tuple outside this frozen candidate pair')
    return struct.pack('>fff', *values)


def decode_gain_values(body):
    """Decode only the 12-byte getter value portion, not its error trailer."""
    if len(body) != 12:
        raise ValueError('Exactly three float32 getter values required')
    return gain_tuple(struct.unpack('>fff', body))


def checked_readback(values, expected):
    observed = tuple(values)
    values = gain_tuple(values)
    # A readback must already equal the representable target. Do not silently
    # round a different readback or accept a partial P/T/I restoration.
    if observed != tuple(expected) or tuple(values) != tuple(expected):
        raise ValueError('Gain readback does not match the complete target')
    return values


def private_nanonis_call(base_call):
    """Reuse the proven transport code with a private schema dictionary.

    The returned unbound function has the same (self, command, args, timeout)
    interface. Its caller must retain its own exact-write permit and used set.
    No global COMMANDS or catalog is modified. Other base schemas are unchanged.
    """
    namespace = dict(base_call.__globals__)
    catalog = copy.deepcopy(namespace['COMMANDS'])
    for name, schema in [('ZCtrl.GainSet', GAIN_SCHEMA), ('Scan.SpeedSet', SPEED_SCHEMA)]:
        if name in catalog:
            if any(catalog[name].get(k) != v for k, v in schema.items()):
                raise ValueError('Existing schema conflicts with official wire order')
        else:
            catalog[name] = copy.deepcopy(schema)
    namespace['COMMANDS'] = catalog
    result = types.FunctionType(base_call.__code__, namespace, base_call.__name__,
                                base_call.__defaults__, base_call.__closure__)
    result.__kwdefaults__ = copy.copy(base_call.__kwdefaults__)
    return result


class OneGainAttempt:
    """A single configuration write, not a stage admission or hardware driver."""
    def __init__(self, mode):
        self.source, self.target = target_pair(mode)
        self.mode = mode
        self.consumed = False

    def execute(self, before_values, claim, send, readback):
        """Callbacks are bound by the root runner; this function never retries.

        claim(command,args) must atomically persist before send(command,args).
        send/readback use the original bounded transport and raw audit. A failed
        callback stops this sequence. No callback performs inverse restoration.
        """
        if self.consumed:
            raise RuntimeError('Gain attempt already consumed')
        checked_readback(before_values, self.source)
        self.consumed = True
        result = {'mode': self.mode, 'before': list(self.source), 'target': list(self.target),
                  'attempted': False, 'acknowledged': False, 'configuration_verified': False,
                  'writer_outcome_unknown': False, 'automatic_retry': False,
                  'automatic_restore': False, 'status': 'not_sent'}
        try:
            result['claim'] = claim('ZCtrl.GainSet', list(self.target))
            result['attempted'] = True
            result['writer_outcome_unknown'] = True
            ack = send('ZCtrl.GainSet', list(self.target))
            result['ack'] = ack
            if ack != {'command': 'ZCtrl.GainSet', 'values': [], 'warning': ''}:
                result['status'] = 'ack_not_accepted_no_followup'
                return result
            result['acknowledged'] = True
            result['writer_outcome_unknown'] = False
            returned = readback('ZCtrl.GainGet', [])
            result['readback'] = returned
            if returned.get('command') != 'ZCtrl.GainGet' or returned.get('warning'):
                raise ValueError('Gain getter response not accepted')
            checked_readback(returned['values'], self.target)
            result.update(status='gain_configured_and_exact_readback_verified', configuration_verified=True)
        except BaseException as exc:
            result['error'] = type(exc).__name__ + ': ' + str(exc)
            result['status'] = ('known_ack_configuration_unverified' if result['acknowledged'] else
                                'write_outcome_unknown' if result['attempted'] else 'claim_failed_no_write')
        return result
