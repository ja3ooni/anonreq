---
title: MiCA Compliance Standards
inclusion: fileMatch
fileMatchPattern: '**/crypto/**,**/dlt/**,**/blockchain/**'
---

# MiCA Compliance Standards

## Crypto-Asset Classification
- **Token Categorization:** Implement a robust classification engine for crypto-assets (e.g., ARTs, EMTs, Utility Tokens) based on MiCA definitions.
- **Regulatory Mapping:** Map each classified crypto-asset to its specific MiCA obligations (e.g., whitepaper requirements, market abuse rules).

## Transaction Monitoring for DLT
- **Blockchain Integration:** Integrate with major public and permissioned blockchains (e.g., Ethereum, Avalanche, Hyperledger Fabric) to ingest transaction data.
- **Wallet Screening:** Implement real-time screening of crypto-asset wallet addresses against sanctions lists and known illicit addresses.
- **Transaction Tracing:** Develop capabilities for tracing the flow of crypto-assets across multiple hops and different blockchains to identify suspicious patterns.

## Market Integrity & Abuse Detection
- **Order Book Surveillance:** For crypto-asset service providers (CASPs), implement surveillance of order books and trading activity to detect market manipulation (e.g., wash trading, spoofing).
- **On-Chain Analytics:** Leverage on-chain data to identify unusual transaction volumes, sudden price movements, or concentrated holdings that could indicate market abuse.

## Reporting & Record-Keeping
- **MiCA-Specific Reporting:** Generate reports for competent authorities (e.g., ESMA, EBA) on market abuse, operational incidents, and significant holdings as required by MiCA.
- **Immutable Records:** Ensure all crypto-asset transaction data and associated compliance decisions are stored in the immutable audit log.
- **Transaction History:** Maintain detailed, auditable records of all crypto-asset transactions, including on-chain and off-chain movements, for a minimum of 7 years.

## Custody & Security
- **Key Management:** For any custody-related features, ensure integration with FIPS 140-2 Level 3+ certified Hardware Security Modules (HSMs) for private key management.
- **Operational Resilience:** Extend DORA standards to cover the specific operational risks associated with Distributed Ledger Technology (DLT) infrastructure.