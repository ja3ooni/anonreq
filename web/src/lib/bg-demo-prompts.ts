/**
 * SYNTHETIC DEMO DATA ONLY. Every name, EGN, IBAN, phone and e-mail below is invented.
 * - EGN values use month 99, which no real EGN (ЕГН) can have.
 * - IBANs use the bank code "TEST", which no Bulgarian bank uses (the check digits are
 *   valid so the gateway's IBAN recognizer still fires in live mode).
 * - E-mails use the reserved example.org domain; phone numbers are 000-padded.
 * Bulgarian wording is pending native review (Ibtisam). See src/messages/REVIEW-bg.md.
 */

export interface StaffDemoPrompt {
  id: string;
  synthetic: true;
  /** Fake identifiers embedded in the prompt, for tests and reviewers. */
  fakeEgn: string | null;
  fakeIban: string | null;
  label: { bg: string; en: string; de: string };
  prompt: string;
}

export const FAKE_EGN_1 = "9999999999";
export const FAKE_EGN_2 = "8899999990";
export const FAKE_IBAN_1 = "BG78 TEST 0000 1234 5678 90";
export const FAKE_IBAN_2 = "BG94TEST99990000000001";

export const STAFF_DEMO_PROMPTS: StaffDemoPrompt[] = [
  {
    id: "social-assistance",
    synthetic: true,
    fakeEgn: FAKE_EGN_1,
    fakeIban: FAKE_IBAN_1,
    label: {
      bg: "Молба за социално подпомагане (синтетична)",
      en: "Social assistance request (synthetic)",
      de: "Antrag auf Sozialhilfe (synthetisch)",
    },
    prompt:
      `[СИНТЕТИЧНИ ДАННИ] Молба от Иван Тестов Примеров, ЕГН ${FAKE_EGN_1}, ` +
      `ж.к. Младост, София, за еднократна помощ, подадена на 14.03.2026. ` +
      `Контакт: ivan.testov@example.org, +359 88 000 0001. ` +
      `Сметка за превод: IBAN ${FAKE_IBAN_1}. ` +
      `Моля, обобщи молбата и подготви кратък учтив отговор до гражданина.`,
  },
  {
    id: "address-registration",
    synthetic: true,
    fakeEgn: FAKE_EGN_2,
    fakeIban: FAKE_IBAN_2,
    label: {
      bg: "Адресна регистрация и местен данък (синтетична)",
      en: "Address registration and local tax (synthetic)",
      de: "Adressregistrierung und Gemeindesteuer (synthetisch)",
    },
    prompt:
      `[СИНТЕТИЧНИ ДАННИ] Мария Пробна Демова (ЕГН ${FAKE_EGN_2}) се премества от Пловдив ` +
      `във Варна от 01.04.2026 и пита как да плати местния данък от сметка ${FAKE_IBAN_2}. ` +
      `Имейл: maria.probna@example.org. ` +
      `Моля, изброй стъпките за адресна регистрация и кои документи са нужни.`,
  },
  {
    id: "no-personal-data",
    synthetic: true,
    fakeEgn: null,
    fakeIban: null,
    label: {
      bg: "Общ въпрос без лични данни",
      en: "General question without personal data",
      de: "Allgemeine Frage ohne personenbezogene Daten",
    },
    prompt:
      "Обясни с три изречения какви са работните часове на центъра за административно обслужване " +
      "и как гражданите могат да запазят час онлайн.",
  },
];
