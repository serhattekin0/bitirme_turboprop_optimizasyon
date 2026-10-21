"""NeuralFoil ile Clark Y, NACA 4412, ARA-D %10 polarları (UIUC koordinatları, aerosandbox veritabanı)."""
import sys
from pathlib import Path

import aerosandbox as asb
import neuralfoil as nf
import numpy as np
import pandas as pd

CIKTI = Path(sys.argv[1])
PROFILLER = {"clarky": "Clark Y", "naca4412": "NACA 4412", "arad10": "ARA-D %10"}
RE_LISTESI = {"re1p2M": 1.2e6, "re2p5M": 2.5e6}
ALFA = np.round(np.arange(-10.0, 20.0001, 0.25), 2)
MODEL = "xlarge"  # NeuralFoil varsayılanı; arkadaşın kontrol değerlerini birebir veriyor
NCRIT = 9.0

for klasor, re in RE_LISTESI.items():
    (CIKTI / klasor).mkdir(parents=True, exist_ok=True)
    for anahtar, ad in PROFILLER.items():
        af = asb.Airfoil(anahtar)
        sonuc = nf.get_aero_from_airfoil(af, alpha=ALFA, Re=re, n_crit=NCRIT, model_size=MODEL)
        df = pd.DataFrame(dict(alpha=ALFA, cl=sonuc["CL"], cd=sonuc["CD"], cm=sonuc["CM"],
                               guven=sonuc["analysis_confidence"]))
        yol = CIKTI / klasor / f"{anahtar}.csv"
        with open(yol, "w", encoding="utf-8") as f:
            f.write(f"# {ad} ({anahtar}), NeuralFoil {nf.__version__ if hasattr(nf, '__version__') else ''} "
                    f"model={MODEL}, Re={re:.3g}, Mach=0, n_crit={NCRIT:g} (pürüzsüz yüzey, serbest geçiş)\n")
            f.write(f"# Koordinatlar: UIUC '{anahtar}' (aerosandbox veritabanı), t/c={af.max_thickness():.4f}, "
                    f"kamburluk={af.max_camber():.4f}\n")
            f.write("# guven: NeuralFoil analysis_confidence (0-1); düşükse o açıdaki değer şüpheli\n")
            df.to_csv(f, index=False, float_format="%.6f")
        ld = df.cl / df.cd
        i = ld.idxmax()
        print(f"{klasor} {ad:<10} en iyi L/D: α={df.alpha[i]:5.2f}°, cl={df.cl[i]:.3f}, cd={df.cd[i]:.5f}, "
              f"L/D={ld[i]:.0f} | cl_max={df.cl.max():.3f} @ {df.alpha[df.cl.idxmax()]:.2f}° | "
              f"cd_min={df.cd.min():.5f} | α0 (cl=0)={np.interp(0, df.cl[(df.alpha>-8)&(df.alpha<5)], df.alpha[(df.alpha>-8)&(df.alpha<5)]):.2f}° | "
              f"cl(5.1°)={np.interp(5.1, df.alpha, df.cl):.3f} | güven min={df.guven.min():.2f}")
