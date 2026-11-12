# Part 4：LTL 形式化规约与测试用例（公共题）

20 道公共题的 LTL 规约、测试用例、参考实现与变异体，以及可重跑全部结论的脚本。

本目录按仓库现有结构放置：题库资产统一在 `codesys_service/` 下，与 `bank/st/`、`bank/cases/` 并列；
跨部分的脚本与文档放在仓库根。

## 目录

```
codesys_service/
├── specs/                    20 份 LTL 规约
├── bank/
│   ├── cases_part4/          20 套测试用例（88 个用例）
│   ├── st_part4/             20 份自写参考实现
│   └── mutants/              40 个变异体
└── st_sim.py                 已修 4 个 bug 的仿真器

tools/verification/           验证脚本 + 运行结果
docs/                         交叉校验报告、仿真器补丁
```

不动 `bank/cases/` 与 `bank/st/`，那是 Part 2 的回归基准，`bank/README.md` 里记录了
`sim（12 题）25/25 用例` 的结果，覆盖掉会让那段说明失效。

## 规模

| 项目 | 数量 |
|---|---|
| LTL 性质 | 264 条 |
| 实质性需求歧义 | 18 条，分布在 16 题 |
| 测试用例 | 88 个 / 754 个扫描周期 |
| 参考实现 | 两套各 20 份（独立编写） |
| 变异体 | 40 个 |

## 基准结果

同一套 88 个用例跑在两套独立编写的实现上：

| 实现 | 通过 |
|---|---|
| `bank/st_part4`（Part 4） | **88/88** |
| `bank/st`（Part 2） | **87/88** |

唯一分歧不是理解不同，是 Part 2 实现里的真实缺陷：`H05_MechArm` 的 `running := TRUE`
无条件赋值，使单步模式按一次 Start 会连续跑完八个动作，退化为单循环。
用例 TC07 断言的是需求行为，因此在那边失败。详情见 `docs/CROSSCHECK.md`。

变异测试 40 个全部检出。

## 复跑

```bash
# 两套实现 × 全部 20 题
python tools/verification/run_suite.py

# 单题（全名或短名都行）
python tools/verification/run_suite.py --task E01_Filling
python tools/verification/run_suite.py --task E01

# 变异测试
python tools/verification/run_mutation.py

# 从运行结果重新生成规约里的用例表与验证数字
python tools/verification/sync_specs.py
```

脚本路径全部相对自身解析，`run_tests.py` 会在 `codesys_service/` 下自动找到，
不需要设置环境变量。若工具链在别处，用 `CODESYS_SERVICE=<目录>` 覆盖。

## 测试用例格式

一题一文件，命名用完整题目编号（`E01_Filling.testcase.json`）。

```json
{
  "task_id":   "E01_Filling",
  "title":     "Automated Filling Line Control",
  "pou":       "E01_Filling",
  "scan_ms":   20,
  "interface": [{"name": "bottleSensor", "dir": "input", "type": "BOOL"}],
  "cases": [
    {
      "id": "TC01",
      "name": "Full production cycle",
      "coverage": "each transition, one actuator at a time, ...",
      "initial_state": "power-up: step 0, all actuators off",
      "steps": [
        {"cycle": 1, "inputs": {"bottleSensor": 1},
         "expect": {"Pump_Motor": 1}, "check": "bottle detected -> cleaning"}
      ]
    }
  ]
}
```

`cases` 的字段对应课程模板的六项；`steps[].check` 进入报告的「测试目的」列。

三条规则：

1. **`inputs` 是持久的。** 上一步置 TRUE 的信号若本步不写仍是 TRUE，撤销须显式写 `0`。
   这条让「按钮按住跨多周期」这类用例可写，也正是变异测试发现盲区的地方。
2. **`expect` 不能为空。** 空对象等于该步不校验任何输出，工具会拒绝。
3. **布尔写 `0`/`1`，状态码写十进制。** `16#8001` 写 `32769`。

四条时序约定（与每份规约的 `Conventions` 一致）：

| 约定 | 含义 |
|---|---|
| 输出延后一周期 | 第 N 周期判定的迁移，输出在第 N+1 周期可见 |
| 按钮为边沿触发 | 按住不放不重复触发 |
| 定时器按真实时间 | 走 `scan_ms` 虚拟时钟，不按 `CycleTime` 累加 |
| 时间累加单位为 ms | `LTIME` 输出按毫秒比较 |

> 注意：`bank/README.md` 里「用例里按钮一律按 0→1 脉冲设计」这句只适用于 `bank/cases/`。
> `cases_part4/` 专门补了「按住不放」与「传感器持续为 TRUE」的场景，
> 因为电平触发与边沿触发在单周期脉冲下行为完全相同，无法区分。

## 命名

仓库里原本有两套命名习惯，都保留：

- 用例文件名用短名：`bank/cases/E01.testcase.json`（Part 2）
- ST 文件名用完整编号：`bank/st/E01_Filling.st`（Part 2）

`cases_part4/` 与 `st_part4/` 统一用完整编号，与 `specs/` 一致。脚本读 `task_id` 字段做映射，
两种写法都能跑。

变异体命名为 `<短名>_<改动>.st`（`E02_no_prev_update.st`），早期 `Q01`–`Q20` 编号已改过来。

## 已知局限

- 规约只覆盖 20 道公共题。自建题的规约待数据集部分交题后补写，格式与工具链已就绪。
- 未执行形式化验证。规约按 `G(前提 -> X 结论)` 书写，与 PLCVerif 的
  `pattern-statechange-betweencycles` 同构，但 PLCVerif 只支持 Siemens SCL，与 CODESYS ST
  不完全兼容；课程提供的验证服务在提交期内返回 ICP 备案拦截（HTTP 403）。该项为选做加分项。
- 每题 2 个变异体，共 40 个。相比工业规模偏小，全部检出应理解为
  「在本组设计的错误类型下有效」，而非「用例已无盲区」——首轮变异测试本身就发现了一处盲区。
