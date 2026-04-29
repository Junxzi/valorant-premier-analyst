/**
 * Static per-player configuration (flags, etc.).
 * Key: puuid. Values are intentionally optional — missing entries are fine.
 */

export type PlayerConfig = {
  /** ISO 3166-1 alpha-2 country codes (lowercase) displayed as flag images. Up to 3. */
  flags?: string[];
};

const PLAYER_CONFIG: Record<string, PlayerConfig> = {
  // 120pingがIGL roster — ISO 3166-1 alpha-2 country codes
  "b6116b2e-cd92-5484-abe9-afa1f8ea5889": { flags: ["jp"] },            // BABYNOYEN
  "2e5e8d6a-b51e-5912-8689-a7a0c8e2abad": { flags: ["jp", "us"] },     // にょにょ
  "cbeb3493-299b-52f1-afb0-6fb54740bcec": { flags: ["jp"] },            // Curush
  "9475cd46-bb6f-5366-b225-68f31f97f3d3": { flags: ["jp"] },            // Syachi
  "fd97d528-2166-55c0-b1a1-b26e856221e6": { flags: ["jp", "nz", "ph"] }, // Tigerin0
  "b00cda07-e0b9-5e21-a113-8b42448fe844": { flags: ["jp"] },            // lisbeth
};

export function getPlayerConfig(puuid: string): PlayerConfig {
  return PLAYER_CONFIG[puuid] ?? {};
}
