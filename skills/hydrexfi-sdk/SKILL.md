---
name: hydrexfi-sdk
description: "Use @hydrexfi/hydrex-sdk on Base for Hydrex Ichi vault deposits/withdrawals via IchiVaultDepositGuard, claiming oHYDX from gauges, and exercising oHYDX via OptionsToken. Will eventually cover voting, manual NFT LP, and gauge stake/unstake. Load when the user mentions Hydrexfi, Hydrex, Ichi vaults, single-sided deposits, or oHYDX."
---

# Hydrex SDK (Ichi + oHYDX)

This revision documents **`@hydrexfi/hydrex-sdk`** ([`hydrexfi/hydrex-sdk`](https://github.com/hydrexfi/hydrex-sdk)) for:

- **Ichi vaults** — ERC-20/native deposit and withdraw calldata targets **`IchiVaultDepositGuard`** (`build*` methods), plus **`IchiVault`** reads and TVL fallback estimates for slippage floors
- **oHYDX rewards** — **`Gauge`** `getReward` calldata (+ reads); **`ClaimRewards`** batch paths through the voter contract
- **oHYDX conversion** — **`OptionsToken`** quote + exercise calldata

The SDK returns `{ calldata, value }` only — submit with viem, ethers, or wagmi.

There is **no Venice-style REST API** — `curl` examples do not apply.

## SDK surface reference (this revision)

| Class | Scope here | Tx target |
|---|---|---|
| `IchiVaultDepositGuard` | `buildDeposit*`, `buildWithdraw*` — encoded calls to the deposit guard | `ICHI_VAULT_DEPOSIT_GUARD_ADDRESSES[chainId]` |
| `IchiVault` | `getVaultInfo`, `estimateDepositShares`, `estimateWithdrawAmounts`, `applySlippage` — **reads / math only** | Bound to vault address for reads |
| `Gauge` | **Claim-only** writes: `getRewardCallParameters` (+ overloads); reads like `getPendingReward` | Gauge contract vs voter (see below) |
| `ClaimRewards` | `getClaimableGaugeAddresses`, `claimRewards*`, `claimRewardToken(s)*` helpers | **`VOTER_ADDRESSES[chainId]`** for claim calldata |
| `OptionsToken` | `getOptionsTokenInfo`, `getExerciseQuote`, exercise / merge calldata builders | Options token (+ `merge` targets veToken) |

## Use when

- Single-sided **Ichi vault** deposit or withdraw on Base via the deposit guard contract.
- **Claim oHYDX** (`getReward`) on one gauge vs **multi-gauge** claims via voter contract helpers on `ClaimRewards`.
- **Quote / exercise** oHYDX (`OptionsToken`), including merge flows.

## Minimal example

Deposit ERC-20 through the guard (**approve `token` → `ICHI_VAULT_DEPOSIT_GUARD_ADDRESSES[chainId]`** first):

```ts
import {
  IchiVaultDepositGuard,
  ICHI_VAULT_DEPLOYER_ADDRESSES,
  ICHI_VAULT_DEPOSIT_GUARD_ADDRESSES,
  ChainId,
} from '@hydrexfi/hydrex-sdk';

const chainId = ChainId.Base;
const { calldata, value } = IchiVaultDepositGuard.buildDepositCallParameters({
  vault: '0xIchiVaultShareToken',
  vaultDeployer: ICHI_VAULT_DEPLOYER_ADDRESSES[chainId],
  token: '0xDepositAsset',
  amount: '1000000',
  minimumProceeds: '1', // use simulation + applySlippage, or IchiVault.estimateDepositShares (see below); never `'0'` in production
  recipient: '0xYourWallet',
});
await walletClient.sendTransaction({
  to: ICHI_VAULT_DEPOSIT_GUARD_ADDRESSES[chainId],
  data: calldata,
  value,
});
```

## Installation

```bash
npm install @hydrexfi/hydrex-sdk   # package name: @hydrexfi/hydrex-sdk
```

## Supported networks (`ChainId`)

| Chain | ID |
|---|---|
| Base mainnet | `8453` (`ChainId.Base`) |
| Base Sepolia | `84532` (`ChainId.BaseSepolia`) |

Published constants **`VOTER_ADDRESSES`, `ICHI_VAULT_DEPOSIT_GUARD_ADDRESSES`, `ICHI_VAULT_DEPLOYER_ADDRESSES` are keyed for Base mainnet in the npm package.** On Sepolia supply your own contract addresses unless/until upstream adds mappings.

## Injected reads

Gauge / options / claim discovery need `readContract` or `readContracts` **bound to the correct contract** (gauge, vault, options token):

```ts
import type { ReadContractFunction, ReadContractsFunction } from '@hydrexfi/hydrex-sdk';

const readContract: ReadContractFunction = ({ functionName, args }) =>
  viemClient.readContract({ address: targetAddress, abi, functionName, args });

const readContracts: ReadContractsFunction = (calls) =>
  Promise.all(calls.map((c) => viemClient.readContract({ ...c, address: targetAddress, abi })));
```

**Amounts:** use **raw integer strings** / `BigintIsh` (wei or token decimals), not human `"1"` for tokens with >0 decimals.

---

## Ichi: reads + deposit / withdraw guard

Vault **reads** (bind `readContracts` to the **vault address**):

```ts
import { IchiVault } from '@hydrexfi/hydrex-sdk';

const info = await IchiVault.getVaultInfo(vaultBoundReadContracts);
// info.allowToken0, info.allowToken1, info.token0, info.token1, info.deposit0Max, deposit1Max, totals…
```

**Slippage floors** — prefer simulating deposit/withdraw with minimums `0`, then **`IchiVault.applySlippage(simulated, slippageBps)`**. If simulation is unavailable, SDK fallbacks (**≥500 bips** enforced inside):

```ts
const minimumProceeds = IchiVault.estimateDepositShares(
  depositUsd,
  vaultTvlUsd,
  info.totalSupply,
  slippageBps,
);

const { amount0: minAmount0, amount1: minAmount1 } = IchiVault.estimateWithdrawAmounts(
  shares,
  info.total0,
  info.total1,
  info.totalSupply,
  slippageBps,
);
```

ERC-20 **deposit**:

```ts
import { IchiVaultDepositGuard, ICHI_VAULT_DEPLOYER_ADDRESSES, ChainId } from '@hydrexfi/hydrex-sdk';

const { calldata, value } = IchiVaultDepositGuard.buildDepositCallParameters({
  vault,
  vaultDeployer: ICHI_VAULT_DEPLOYER_ADDRESSES[ChainId.Base],
  token,
  amount,
  minimumProceeds,
  recipient,
});
```

**Native ETH deposit** uses `buildNativeDepositCallParameters` (`value` carries the wei); **`buildWithdrawCallParameters`** and **`buildNativeWithdrawCallParameters`** need `vault`, `vaultDeployer`, `shares`, `recipient`, `minAmount0`, `minAmount1`. **Approve the guard for vault share tokens before withdraw.**

---

## Claiming oHYDX from gauges

### Single gauge — `Gauge` (→ **gauge contract**)

```ts
import { Gauge } from '@hydrexfi/hydrex-sdk';

// Pick the overload that matches your gauge; send calldata to the gauge contract `to`
const { calldata } = Gauge.getRewardCallParameters();
//Gauge.getRewardCallParameters('0xBeneficiary');
//Gauge.getRewardCallParameters('0xUser', ['0xRewardToken']);

const pending = await Gauge.getPendingReward('0xUser', gaugeBoundReadContract);
const pendingDual = await Gauge.getPendingReward('0xUser', gaugeBoundReadContract, '0xRewardToken');
```

### Batch via voter — `ClaimRewards` (→ **`VOTER_ADDRESSES`**)

Discovery requires **`GaugeRewardReadInput[]`** (address + injected read + optional reward token):

```ts
import { ClaimRewards } from '@hydrexfi/hydrex-sdk';

const gauges = [
  { gaugeAddress: '0xGauge1', readContract: readGauge1AsBound },
  { gaugeAddress: '0xGauge2', readContract: readGauge2AsBound, rewardTokenAddress: '0xoHYDXOrOther' },
];
const claimable = await ClaimRewards.getClaimableGaugeAddresses('0xUser', gauges);

const batchClaim = ClaimRewards.claimRewardsCallParameters({ gaugeAddresses: claimable });

const claimForOther = ClaimRewards.claimRewardsForCallParameters({
  gaugeAddresses: ['0xGauge1'],
  claimFor: '0xOther',
});

const claimSpecificTokens = ClaimRewards.claimRewardTokensCallParameters({
  claims: [{ gaugeAddress: '0xGauge1', tokens: ['0xToken'] }],
});
```

`claimRewardToken*` / `claimRewards*ToRecipient*` helpers also exist — see [`src/classes/claimRewards.ts`](https://github.com/hydrexfi/hydrex-sdk/blob/main/src/classes/claimRewards.ts) in-repo.

---

## Converting oHYDX (`OptionsToken`)

Reads use `readContracts` bound to **options token**; `getNextVeTokenId` uses **veToken** `readContract`.

```ts
import { OptionsToken } from '@hydrexfi/hydrex-sdk';

const info = await OptionsToken.getOptionsTokenInfo(optionsBoundReadContracts);
const quote = await OptionsToken.getExerciseQuote('1000000000000000000', optionsBoundReadContracts);
// approve quote.paymentToken for ≥ quote.paymentAmount to the options token contract

// Liquid HYDX path — calldata `to` = options token
const liquid = OptionsToken.exerciseToLiquidHydxCallParameters({
  amount: '1000000000000000000',
  maxPaymentAmount: quote.paymentAmount,
  recipient: '0xYourWallet',
  deadlineSeconds: 600,
});

// New veNFT — `to` = options token
const veOnly = OptionsToken.exerciseToProtocolAccountCallParameters({
  amount: '1000000000000000000',
  recipient: '0xYourWallet',
});

const nextVeTokenId = await OptionsToken.getNextVeTokenId(veTokenReadContract);
const [exerciseVe, mergeVe] = OptionsToken.exerciseToProtocolAccountAndMergeCallParameters({
  amount: '1000000000000000000',
  recipient: '0xYourWallet',
  nextVeTokenId,
  targetTokenId: 42n,
});
// Tx 1: exerciseVe → options token. Tx 2: mergeVe → veToken (`VE_TOKEN_ADDRESSES[chainId]` in SDK constants)
```

---

## Key contract addresses (SDK constants, Base mainnet)

| Constant | Role |
|---|---|
| `VOTER_ADDRESSES[8453]` | `0xc69E3eF39E3fFBcE2A1c570f8d3ADF76909ef17b` — `ClaimRewards` calldata `to` |
| `ICHI_VAULT_DEPOSIT_GUARD_ADDRESSES[8453]` | `0x9A0EBEc47c85fD30F1fdc90F57d2b178e84DC8d8` — deposits / withdraws |
| `ICHI_VAULT_DEPLOYER_ADDRESSES[8453]` | `0x7d11De61c219b70428Bb3199F0DD88bA9E76bfEE` — required deposit/withdraw parameter |
| `VE_TOKEN_ADDRESSES[8453]` | `0x25B2ED7149fb8A05f6eF9407d9c8F878f59cd1e1` — second tx of `exerciseToProtocolAccountAndMergeCallParameters` (`merge` calldata) |

Gauge and options-token addresses are **deployment-specific.**

```ts
import {
  ChainId,
  VOTER_ADDRESSES,
  ICHI_VAULT_DEPOSIT_GUARD_ADDRESSES,
  ICHI_VAULT_DEPLOYER_ADDRESSES,
  VE_TOKEN_ADDRESSES,
} from '@hydrexfi/hydrex-sdk';
```

---

## Errors

| Symptom | Likely cause | Fix |
|---|---|---|
| `encodeFunctionData` / tx revert | Old skill names (`depositCallParameters`) — SDK uses **`buildDepositCallParameters`** | Match method names in [`src/classes/ichiVaultDepositGuard.ts`](https://github.com/hydrexfi/hydrex-sdk/blob/main/src/classes/ichiVaultDepositGuard.ts) |
| Ichi revert | Wrong `vaultDeployer` or missing **`minimumProceeds` / withdraw mins** | Use `ICHI_VAULT_DEPLOYER_ADDRESSES`; simulate then `applySlippage`, or fallback estimators |
| Claim batch revert | Sending voter calldata **`to`** a gauge contract | Batch claims → **`VOTER_ADDRESSES`**; single `getReward` → **gauge** |
| `getClaimableGaugeAddresses` throws | Mis-bound `readContract` or wrong `earned` signature | Pass per-gauge `GaugeRewardReadInput`; supply `rewardTokenAddress` when gauge uses 2-arg `earned` |
| Exercise revert | Stale approval vs TWAP | Refresh `getExerciseQuote` + re-approve payment token |
| Merge second tx fails | Stale `nextVeTokenId` | Re-read immediately before building both calls |

## Gotchas

- **Deposits and withdraws always go through the deposit guard**, not the raw vault contract, for the encoded paths above.
- **Withdrawals require approval** of **vault share tokens** (vault address = share token) to the guard.
- **SDK publishes v1.x** (`package.json`); verify signatures against tagged release if pinning behavior.

## Related skills

- [`venice-errors`](../venice-errors/SKILL.md) — HTTP-style errors / backoff analogy for RPC and wallet failures
