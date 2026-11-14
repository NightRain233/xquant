# Trading 迁移研究输出

这里保存从同级 `trading` 仓库迁入的历史研究脚本输出。每次研究使用一个带日期的文件名或目录，并保留：

- 运行脚本和参数
- 输入数据的时间范围
- JSON/CSV 原始结果
- 对应的说明或复核笔记

这些输出只用于复现和比较，不会被 trading 运行时读取。新的正式研究优先使用独立 slug 目录，例如：

```text
outputs/<experiment-slug>/
docs/notes/<experiment-slug>-review.md
scripts/trading_research/<experiment>.py
```

`TRADING_ROOT` 用于指定行情和 trading 策略代码的位置；默认值是 xquant 的同级 `../trading`。
