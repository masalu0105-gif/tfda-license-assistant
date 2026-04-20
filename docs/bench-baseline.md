# TFDA bench baseline

- source: synthetic@/tmp/tfda_bench_d0enxsst
- rows: 150000
- cold_load_ms: 2544.4

| scenario | p50 (ms) | p95 (ms) | n_hits |
|---|---:|---:|---:|
| company__醫兆 | 517.52 | 545.03 | 60000 |
| manufacturer__ARKRAY | 806.87 | 845.16 | 60000 |
| manufacturer__Sysmex | 1016.03 | 1036.87 | 22500 |
| reagent__HbA1c | 5544.83 | 5666.8 | 30000 |
| keyword__尿液 | 386.82 | 403.66 | 22500 |
| product__Glucose | 1919.22 | 1999.36 | 30000 |
| license__exact | 4764.25 | 4944.79 | 150000 |
| cross_filter__3way | 1814.21 | 1840.61 | 7500 |

## 結論
- P5.2 pre-index 觸發：**需要**（company__醫兆, manufacturer__ARKRAY, manufacturer__Sysmex, reagent__HbA1c, product__Glucose, license__exact, cross_filter__3way）
- P5.3 normalize 快取觸發：**需要**