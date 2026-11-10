# 公共题库 20 题回归资产

对 `data/tasks.json`（大作业题库）全部 20 道题的参考实现与测试用例，
作为工具链（lint / CODESYS 编译 / sim 仿真）的回归基准。

## 内容

- `st/`：20 道题的参考 ST 实现（E01~E06 / M01~M08 / H01~H06），
  文件名即 POU 名；含 DUT 的题目（M01/M02/H03）把 `TYPE...END_TYPE`
  写在文件头部，由服务自动拆成独立 DUT 对象。
- `cases/`：12 道题的 sim 测试用例（E01/E03/E05/E06/M03/M04/M05/M06/M07/M08/H04/H06），
  覆盖定时器（TON/TOF）、`hold_ms`、数组下标断言、16# 状态码、
  迟滞逻辑、状态机时序、STRING 下标与 Standard `LEN` 等。
  其余 8 题用到结构体数组（M01/M02/H03）或尚未覆盖的复杂逻辑，仅做
  lint+编译回归。

## 基准结果（2026-11-10）

| 阶段          | 结果    |
| ------------- | ------- |
| lint          | 20/20   |
| CODESYS 真编译 | 20/20   |
| sim（12 题）   | 25/25 用例 |

## 复跑

```bash
python st_lint.py bank/st/
python codesys_compile.py --st bank/st/ --project templates/template.project --out out/bank_compile.json
# sim（12 题逐个跑）
for t in E01 E03 E05 E06 M03 M04 M05 M06 M07 M08 H04 H06; do
  python run_tests.py --case bank/cases/${t}.testcase.json --st bank/st/${t}*.st --backend sim
done
```

## 已知说明

- M08（IPv4 解析）使用 Standard Library 的 `LEN` 获取字符串长度，
  再用 1 基下标扫描 STRING；这也作为 sim 字符串能力的回归用例。
- H04 的参考实现用 `DINT / ARRAY[0..7] OF DINT` 替代题面的 VARIANT
  ——纯 ST 无法对 VARIANT 做下标存取，编译侧 VARIANT 绑定另行验证。
- 用例里按钮/触发信号一律按 0→1 脉冲设计（相邻两步同值不会产生上升沿），
  状态机断言考虑一拍扫描延迟。
