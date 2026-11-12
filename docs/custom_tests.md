# Custom Question Bank test case summary

Test cases follow the repository format used by `codesys_service/run_tests.py`.

| ID | POU | Cases | Steps |
| --- | --- | --- | --- |
| C01 | `FB_C01` | 2 | 16 |
| C02 | `FB_C02` | 2 | 10 |
| C03 | `FB_C03` | 2 | 9 |
| C04 | `FB_C04` | 2 | 9 |
| C05 | `FB_C05` | 2 | 11 |
| C06 | `FB_C06` | 3 | 10 |
| C07 | `FB_C07` | 2 | 8 |
| C08 | `FB_C08` | 3 | 7 |
| C09 | `FB_C09` | 3 | 8 |
| C10 | `FB_C10` | 3 | 13 |
| C11 | `FB_C11` | 1 | 14 |
| C12 | `FB_C12` | 3 | 13 |

## How to run

```bash
cd codesys_service
python run_tests.py --case bank/custom/cases/C01.testcase.json --st bank/custom/st/FB_C01.st --backend dry
python run_tests.py --case bank/custom/cases/C01.testcase.json --st bank/custom/st/FB_C01.st --backend sim
```

The `dry` backend checks the case structure and cross-checks variable names/types against the ST. The `sim` backend executes the reference ST scan by scan.
