# 02 — Customer lifetime value

Customer-grain CLV: BG/NBD, Gamma-Gamma, out-of-fold Ridge.

- Data engineering: `mart_clv_customer` at snapshot T
- Development: `/clv` studio
- Production: **Azure**, Sunday score job (separate from the mix-model Monday parent)

Live: `/clv/data-engineering` · `/clv` · `/clv/production`
