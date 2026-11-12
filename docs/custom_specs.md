# Custom Question Bank LTL specification summary

Each question has three properties: a safety/invariant property, a response/sequence property and a recovery/termination property. Atoms are defined in the corresponding JSON file under `specs/custom/`.

| ID | POU | Properties |
| --- | --- | --- |
| C01 | `FB_C01` | P1: Defective part is rejected; P2: Pusher retracts; P3: Batch full stops the conveyor |
| C02 | `FB_C02` | P1: Two-hand start; P2: Part interlock; P3: Anti-tiedown detects a held button |
| C03 | `FB_C03` | P1: Vehicle opens the gate; P2: Beam opens and warns; P3: Delayed close |
| C04 | `FB_C04` | P1: Overload trips all contactors; P2: Star-delta interlock; P3: Timed transition |
| C05 | `FB_C05` | P1: Emergency stop removes all actuators; P2: Foam requires conveyor; P3: Cycle eventually completes |
| C06 | `FB_C06` | P1: Obstacle prevents closing; P2: Motor interlock; P3: Automatic close |
| C07 | `FB_C07` | P1: In-range bottle is accepted; P2: Out-of-range bottle is rejected; P3: Gates are mutually exclusive |
| C08 | `FB_C08` | P1: Valve implies pump; P2: Stop removes all outputs; P3: Started cycle terminates |
| C09 | `FB_C09` | P1: Zone 1 moves into a free zone 2; P2: Zone 1 full condition; P3: Jam stops all motors |
| C10 | `FB_C10` | P1: Lockout removes all combustion outputs; P2: Fuel requires proven flame; P3: Failed ignition locks out |
| C11 | `FB_C11` | P1: Layer completion pushes; P2: Full pallet stops conveyor; P3: Push pulse ends |
| C12 | `FB_C12` | P1: Curtain stops the conveyor; P2: Safety stop stops the conveyor; P3: Valid sequence activates muting |

## Abstraction notes

- LTL is evaluated over discrete scan-cycle states.
- Numeric thresholds are represented as derived atoms (for example `HeightInRange`).
- Timer conditions are represented as internal atoms mapped to the reference implementation's `.Q` flag.
- The reference ST is only a validation artifact and must not be given to the coding agent.
