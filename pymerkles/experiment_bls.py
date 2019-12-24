from py_ecc import bls

# Flag to make BLS active or not. Used for testing, do not ignore BLS in production unless you know what you are doing.
bls_active = True

STUB_SIGNATURE = b'\x11' * 96
STUB_PUBKEY = b'\x22' * 48
STUB_COORDINATES = bls.api.signature_to_G2(bls.sign(b"", 0, b"\0" * 8))


def bls_verify(pubkey, message_hash, signature, domain):
    return bls.verify(message_hash=message_hash, pubkey=pubkey,
                      signature=signature, domain=domain)


def bls_verify_multiple(pubkeys, message_hashes, signature, domain):
    return bls.verify_multiple(pubkeys=pubkeys, message_hashes=message_hashes,
                               signature=signature, domain=domain)


def bls_aggregate_pubkeys(pubkeys):
    return bls.aggregate_pubkeys(pubkeys)


def bls_aggregate_signatures(signatures):
    return bls.aggregate_signatures(signatures)


def bls_sign(message_hash, privkey, domain):
    return bls.sign(message_hash=message_hash, privkey=privkey,
                    domain=domain)


def bls_signature_to_G2(signature):
    return bls.api.signature_to_G2(signature)
