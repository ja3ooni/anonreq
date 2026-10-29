import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

import {
  createMinimalDocx,
  createMinimalPdf,
  extractFileText,
} from "./file-extract.ts";

test("extracts text from .txt and .json files", () => {
  const bytes = new TextEncoder().encode("IBAN DE89 3704 0044 0532 0130 00 für Anna Schmidt");
  const txtResult = extractFileText(bytes, "bank-ticket.txt");
  assert.equal(txtResult.format, "txt");
  assert.equal(txtResult.truncated, false);
  assert.ok(txtResult.text.includes("DE89 3704 0044 0532 0130 00"));

  const jsonBytes = new TextEncoder().encode(JSON.stringify({ ticket: { id: 8811, kvnr: "A123456780" } }));
  const jsonResult = extractFileText(jsonBytes, "claim.json");
  assert.equal(jsonResult.format, "json");
  assert.ok(jsonResult.text.includes("A123456780"));
});

test("extracts text from generated and real .docx archives", () => {
  const sampleDocx = createMinimalDocx([
    "Kreditkarten- & Kontoprüfung Frankfurt",
    "Kunde: Jörg Müller, IBAN: DE89 3704 0044 0532 0130 00, Steuer-ID: 86095742719",
  ]);
  const extracted = extractFileText(sampleDocx, "pilot-ticket.docx");
  assert.equal(extracted.format, "docx");
  assert.ok(extracted.text.includes("Jörg Müller"));
  assert.ok(extracted.text.includes("86095742719"));

  // Also test the real repository .docx file (Deflate-compressed OOXML)
  const realDocxPath = resolve(process.cwd(), "..", "AnonReq_Requirements_v1.0.docx");
  const realBytes = new Uint8Array(readFileSync(realDocxPath));
  const realExtracted = extractFileText(realBytes, "AnonReq_Requirements_v1.0.docx");
  assert.equal(realExtracted.format, "docx");
  assert.ok(realExtracted.charCount > 100);
  assert.ok(realExtracted.text.includes("AnonReq"));
});

test("extracts text from .pdf files", () => {
  const pdfBytes = createMinimalPdf([
    "Schadensmeldung Kfz - Frankfurt",
    "Versicherte: Anna Schmidt, KVNR: A123456780",
    "IBAN: DE89370400440532013000",
  ]);
  const extracted = extractFileText(pdfBytes, "schadensmeldung.pdf");
  assert.equal(extracted.format, "pdf");
  assert.ok(extracted.text.includes("Anna Schmidt"));
  assert.ok(extracted.text.includes("A123456780"));
  assert.ok(extracted.text.includes("DE89370400440532013000"));
});

