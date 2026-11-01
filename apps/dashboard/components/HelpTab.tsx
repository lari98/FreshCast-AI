import type { Strings } from "@/lib/i18n";

export function HelpTab({ t }: { t: Strings }) {
  return (
    <>
      <section aria-labelledby="help-h" className="card">
        <h2 id="help-h">{t.helpTitle}</h2>
        <h3>{t.helpFlowTitle}</h3>
        <ol>
          <li>{t.helpFlow1}</li>
          <li>{t.helpFlow2}</li>
          <li>{t.helpFlow3}</li>
          <li>{t.helpFlow4}</li>
        </ol>
      </section>
      <section aria-labelledby="gloss-h" className="card">
        <h2 id="gloss-h">{t.helpGlossary}</h2>
        <ul>
          {[t.gWape, t.gBias, t.gInterval, t.gSafety, t.gFefo, t.gFour, t.gNews].map((g) => (
            <li key={g}>{g}</li>
          ))}
        </ul>
        <p className="hint">{t.helpPrivacy}</p>
      </section>
    </>
  );
}
