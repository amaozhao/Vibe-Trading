import { Link } from "react-router-dom";
import { ArrowRight, Bot, BarChart3, Zap, UserCircle2 } from "lucide-react";
import { useTranslation, type TranslationKey } from "@/lib/i18n";

export function Home() {
  const { t } = useTranslation();
  const FEATURES = [
    { icon: Bot, titleKey: "home.feature.agent.title", descKey: "home.feature.agent.desc" },
    { icon: BarChart3, titleKey: "home.feature.backtest.title", descKey: "home.feature.backtest.desc" },
    { icon: Zap, titleKey: "home.feature.streaming.title", descKey: "home.feature.streaming.desc" },
    { icon: UserCircle2, titleKey: "home.feature.replay.title", descKey: "home.feature.replay.desc" },
  ] satisfies Array<{ icon: typeof Bot; titleKey: TranslationKey; descKey: TranslationKey }>;

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-8">
      <div className="max-w-2xl text-center space-y-6">
        <h1 className="text-4xl font-bold tracking-tight">{t("home.title")}</h1>
        <p className="text-lg text-muted-foreground">{t("home.subtitle")}</p>
        <Link
          to="/agent"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:opacity-90 transition"
        >
          {t("home.startResearch")} <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-16 max-w-5xl w-full">
        {FEATURES.map(({ icon: Icon, titleKey, descKey }) => (
          <div key={titleKey} className="border rounded-lg p-6 space-y-3">
            <Icon className="h-8 w-8 text-primary" />
            <h3 className="font-semibold">{t(titleKey)}</h3>
            <p className="text-sm text-muted-foreground">{t(descKey)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
