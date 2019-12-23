from pymerkles.complex import Container, List, Vector
from pymerkles.basic import uint8, uint64, boolean
from pymerkles.bytes32 import Bytes32
from pymerkles.bitfields import BitList as Bitlist, BitVector as Bitvector
from pymerkles.tree import merkle_hash

byte = uint8
Bytes1 = Vector[byte, 1]
Bytes4 = Vector[byte, 4]
Bytes8 = Vector[byte, 8]
Bytes48 = Vector[byte, 48]
Bytes96 = Vector[byte, 96]


class Slot(uint64):
    pass


class Epoch(uint64):
    pass


class CommitteeIndex(uint64):
    pass


class ValidatorIndex(uint64):
    pass


class Gwei(uint64):
    pass


class Root(Bytes32):
    pass


class Version(Bytes4):
    pass


class DomainType(Bytes4):
    pass


class Domain(Bytes8):
    pass


class BLSPubkey(Bytes48):
    pass


class BLSSignature(Bytes96):
    pass


def ceillog2(x: uint64) -> int:
    return (x - 1).bit_length()


FAR_FUTURE_EPOCH = Epoch(2**64 - 1)
BASE_REWARDS_PER_EPOCH = 4
DEPOSIT_CONTRACT_TREE_DEPTH = 2**5
SECONDS_PER_DAY = 86400
JUSTIFICATION_BITS_LENGTH = 4
ENDIANNESS = 'little'
MAX_COMMITTEES_PER_SLOT = 2**6
TARGET_COMMITTEE_SIZE = 2**7
MAX_VALIDATORS_PER_COMMITTEE = 2**11
MIN_PER_EPOCH_CHURN_LIMIT = 2**2
CHURN_LIMIT_QUOTIENT = 2**16
SHUFFLE_ROUND_COUNT = 90
MIN_GENESIS_ACTIVE_VALIDATOR_COUNT = 2**14
MIN_GENESIS_TIME = 1578009600
MIN_DEPOSIT_AMOUNT = Gwei(2**0 * 10**9)
MAX_EFFECTIVE_BALANCE = Gwei(2**5 * 10**9)
EJECTION_BALANCE = Gwei(2**4 * 10**9)
EFFECTIVE_BALANCE_INCREMENT = Gwei(2**0 * 10**9)
GENESIS_SLOT = Slot(0)
GENESIS_EPOCH = Epoch(0)
BLS_WITHDRAWAL_PREFIX = Bytes1(b'\x00')
SECONDS_PER_SLOT = 12
MIN_ATTESTATION_INCLUSION_DELAY = 2**0
SLOTS_PER_EPOCH = 2**5
MIN_SEED_LOOKAHEAD = 2**0
MAX_SEED_LOOKAHEAD = 2**2
SLOTS_PER_ETH1_VOTING_PERIOD = 2**10
SLOTS_PER_HISTORICAL_ROOT = 2**13
MIN_VALIDATOR_WITHDRAWABILITY_DELAY = 2**8
PERSISTENT_COMMITTEE_PERIOD = 2**11
MIN_EPOCHS_TO_INACTIVITY_PENALTY = 2**2
EPOCHS_PER_HISTORICAL_VECTOR = 2**16
EPOCHS_PER_SLASHINGS_VECTOR = 2**13
HISTORICAL_ROOTS_LIMIT = 2**24
VALIDATOR_REGISTRY_LIMIT = 2**40
BASE_REWARD_FACTOR = 2**6
WHISTLEBLOWER_REWARD_QUOTIENT = 2**9
PROPOSER_REWARD_QUOTIENT = 2**3
INACTIVITY_PENALTY_QUOTIENT = 2**25
MIN_SLASHING_PENALTY_QUOTIENT = 2**5
MAX_PROPOSER_SLASHINGS = 2**4
MAX_ATTESTER_SLASHINGS = 2**0
MAX_ATTESTATIONS = 2**7
MAX_DEPOSITS = 2**4
MAX_VOLUNTARY_EXITS = 2**4
DOMAIN_BEACON_PROPOSER = DomainType((0).to_bytes(length=4, byteorder='little'))
DOMAIN_BEACON_ATTESTER = DomainType((1).to_bytes(length=4, byteorder='little'))
DOMAIN_RANDAO = DomainType((2).to_bytes(length=4, byteorder='little'))
DOMAIN_DEPOSIT = DomainType((3).to_bytes(length=4, byteorder='little'))
DOMAIN_VOLUNTARY_EXIT = DomainType((4).to_bytes(length=4, byteorder='little'))
SAFE_SLOTS_TO_UPDATE_JUSTIFIED = 2**3
ETH1_FOLLOW_DISTANCE = 2**10
TARGET_AGGREGATORS_PER_COMMITTEE = 2**4
RANDOM_SUBNETS_PER_VALIDATOR = 2**0
EPOCHS_PER_RANDOM_SUBNET_SUBSCRIPTION = 2**8


class Fork(Container):
    previous_version: Version
    current_version: Version
    epoch: Epoch  # Epoch of latest fork


class Checkpoint(Container):
    epoch: Epoch
    root: Root


class Validator(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32  # Commitment to pubkey for withdrawals
    effective_balance: Gwei  # Balance at stake
    slashed: boolean
    # Status epochs
    activation_eligibility_epoch: Epoch  # When criteria for activation were met
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch  # When validator can withdraw funds


class AttestationData(Container):
    slot: Slot
    index: CommitteeIndex
    # LMD GHOST vote
    beacon_block_root: Root
    # FFG vote
    source: Checkpoint
    target: Checkpoint


class IndexedAttestation(Container):
    attesting_indices: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    signature: BLSSignature


class PendingAttestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    inclusion_delay: Slot
    proposer_index: ValidatorIndex


class Eth1Data(Container):
    deposit_root: Root
    deposit_count: uint64
    block_hash: Bytes32


class HistoricalBatch(Container):
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]


class DepositMessage(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei


class DepositData(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    signature: BLSSignature  # signing over DepositMessage


class BeaconBlockHeader(Container):
    slot: Slot
    parent_root: Root
    state_root: Root
    body_root: Root


class AttesterSlashing(Container):
    attestation_1: IndexedAttestation
    attestation_2: IndexedAttestation


class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    signature: BLSSignature


class Deposit(Container):
    proof: Vector[Bytes32, DEPOSIT_CONTRACT_TREE_DEPTH + 1]  # Merkle path to deposit data list root
    data: DepositData


class VoluntaryExit(Container):
    epoch: Epoch  # Earliest epoch when voluntary exit can be processed
    validator_index: ValidatorIndex


class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, SLOTS_PER_ETH1_VOTING_PERIOD]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Attestations
    previous_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    current_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint  # Previous epoch snapshot
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint


class SignedVoluntaryExit(Container):
    message: VoluntaryExit
    signature: BLSSignature


class SignedBeaconBlockHeader(Container):
    message: BeaconBlockHeader
    signature: BLSSignature


class ProposerSlashing(Container):
    proposer_index: ValidatorIndex
    signed_header_1: SignedBeaconBlockHeader
    signed_header_2: SignedBeaconBlockHeader


class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]


class BeaconBlock(Container):
    slot: Slot
    parent_root: Root
    state_root: Root
    body: BeaconBlockBody


class SignedBeaconBlock(Container):
    message: BeaconBlock
    signature: BLSSignature


class AggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: Attestation
    selection_proof: BLSSignature

state = BeaconState(
    genesis_time=123,
    eth1_data=Eth1Data(block_hash=b"\x42" *32, deposit_count=12),
    latest_block_header=BeaconBlockHeader(body_root=b"\x33" *32),
    randao_mixes=[b"\x22" *32] * EPOCHS_PER_HISTORICAL_VECTOR,
)
print(state)

