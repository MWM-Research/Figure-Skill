# Figure Skill 测试案例

这里集中保存 Figure Skill 的人工测试结果。案例不仅展示最终图片，也保留可编辑源文件、输入、生成脚本、数据溯源和机器可读 QA，方便团队成员判断能力边界并复现实验。

| 编号 | 案例 | 路由 | 验证重点 | 状态 |
| --- | --- | --- | --- | --- |
| 01 | [StreamBridge++ CVPR Figure](01-streambridge-cvpr-figure/) | Hybrid Composite | Raster/Vector 表达分工、定量数据溯源、SVG/PDF/PNG 交付 | ✅ Pass |

## 收录约定

- 使用 `NN-case-name/` 编号，后续案例依次增加；
- 最少保留案例说明、最终 PNG 和 QA 报告；
- 可复现案例同时保留输入、源文件、脚本和 provenance；
- 不提交 API Key、Authorization、未脱敏日志或成员本机绝对路径；
- 测试素材默认仅用于内部验证，不自动视为论文可用数据或已发表结果。
