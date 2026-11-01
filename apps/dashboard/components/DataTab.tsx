import type { Strings } from "@/lib/i18n";
import type { DashboardData, Lang } from "@/lib/types";
import { QualityPanel } from "./QualityPanel";
import { UploadPanel } from "./UploadPanel";

interface Props {
  data: DashboardData;
  onData: (d: DashboardData) => void;
  onReset: () => void;
  lang: Lang;
  t: Strings;
}

export function DataTab({ data, onData, onReset, lang, t }: Props) {
  const upload = data.source === "upload";
  return (
    <>
      <section aria-labelledby="src-h" className="card">
        <h2 id="src-h">{t.dataTitle}</h2>
        <p>
          <strong>{t.sourceLabel}:</strong> {upload ? t.sourceUpload : t.sourceDemo}
        </p>
      </section>
      <UploadPanel t={t} onData={onData} onReset={onReset} showReset={upload} />
      {data.quality && <QualityPanel quality={data.quality} lang={lang} t={t} />}
    </>
  );
}
