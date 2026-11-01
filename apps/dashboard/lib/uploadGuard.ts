/**
 * Browser-side first line of defence for uploads. The API repeats every check
 * (never trust the client); this only gives fast, friendly feedback and stops an
 * obviously wrong file before it leaves the machine.
 */

export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
export const ALLOWED_EXTENSIONS = [".csv", ".tsv", ".txt"];
const EXECUTABLE = /\.(exe|dll|bat|cmd|com|scr|msi|ps1|vbs|js|jse|wsf|jar|lnk|sh|py|php|hta|reg)(\.|$)/i;

/** First bytes of formats that are not CSV text (executables, archives, documents, images). */
const SIGNATURES: number[][] = [
  [0x4d, 0x5a], // MZ: Windows executable
  [0x7f, 0x45, 0x4c, 0x46], // ELF
  [0xcf, 0xfa, 0xed, 0xfe], // Mach-O
  [0xca, 0xfe, 0xba, 0xbe], // Java class
  [0x50, 0x4b, 0x03, 0x04], // ZIP, Office, JAR
  [0x50, 0x4b, 0x05, 0x06],
  [0xd0, 0xcf, 0x11, 0xe0], // legacy Office
  [0x25, 0x50, 0x44, 0x46], // PDF
  [0x1f, 0x8b], // gzip
  [0x42, 0x5a, 0x68], // bzip2
  [0x37, 0x7a, 0xbc, 0xaf], // 7z
  [0x52, 0x61, 0x72, 0x21], // RAR
  [0x89, 0x50, 0x4e, 0x47], // PNG
  [0xff, 0xd8, 0xff], // JPEG
  [0x23, 0x21], // #! script
];

export type UploadProblem = "type" | "size" | "binary";

export function hasBinarySignature(bytes: Uint8Array): boolean {
  const start = bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf ? 3 : 0; // skip UTF-8 BOM
  return SIGNATURES.some((sig) => sig.every((b, i) => bytes[start + i] === b));
}

function readHead(file: Blob, n = 16): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.readAsArrayBuffer(file.slice(0, n));
  });
}

/** Returns the first problem found, or null when the file may be sent. */
export async function checkUpload(file: File): Promise<UploadProblem | null> {
  const name = file.name;
  const okName =
    !/[\\/\0:]|\.\./.test(name) && !EXECUTABLE.test(name) && ALLOWED_EXTENSIONS.some((e) => name.toLowerCase().endsWith(e));
  if (!okName) return "type";
  if (file.size > MAX_UPLOAD_BYTES) return "size";
  try {
    if (hasBinarySignature(await readHead(file))) return "binary";
  } catch {
    return "binary"; // unreadable file: do not send it
  }
  return null;
}
