/**
 * Bulgarian EGN (ЕГН) validation for the mock recognizer.
 * Format YYMMDD + 3-digit region/sequence + check digit. Month encodes the century:
 * 01-12 → 19xx, 21-32 → 18xx, 41-52 → 20xx. Check digit: Σ dᵢ·wᵢ mod 11 (10 → 0).
 * No future-date check, on purpose: synthetic demo EGNs use birth year 2099.
 */

const WEIGHTS = [2, 4, 8, 5, 10, 9, 7, 3, 6];

export function egnBirthDate(egn: string): { year: number; month: number; day: number } | null {
  if (!/^\d{10}$/.test(egn)) {
    return null;
  }
  const yy = Number(egn.slice(0, 2));
  let month = Number(egn.slice(2, 4));
  const day = Number(egn.slice(4, 6));
  let year: number;
  if (month >= 1 && month <= 12) {
    year = 1900 + yy;
  } else if (month >= 21 && month <= 32) {
    year = 1800 + yy;
    month -= 20;
  } else if (month >= 41 && month <= 52) {
    year = 2000 + yy;
    month -= 40;
  } else {
    return null;
  }
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (day < 1 || day > daysInMonth) {
    return null;
  }
  return { year, month, day };
}

export function egnChecksumDigit(firstNine: string): number {
  const sum = [...firstNine].reduce((total, digit, index) => total + Number(digit) * (WEIGHTS[index] ?? 0), 0);
  const remainder = sum % 11;
  return remainder === 10 ? 0 : remainder;
}

export function isValidEgn(egn: string): boolean {
  return egnBirthDate(egn) !== null && egnChecksumDigit(egn.slice(0, 9)) === Number(egn[9]);
}
