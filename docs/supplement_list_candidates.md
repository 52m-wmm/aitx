# 3c 膳食补充剂受控名单：候选（待审，未写入配置）

> 2026-11-05 整理。出处：NIH ODS 膳食补充剂标签数据库 DSLD（api.ods.od.nih.gov/dsld/v9，官方接口）。
> 判定方法：按成分名检索，在返回的标签里**精确匹配成分名**（全文检索会把磷脂酰丝氨酸、多种维生素等算进来，必须精确筛）。
> 原始结果存 `.cache/dsld/candidates.json`（不进仓库）。

| 成分 | DSLD 结果 | 示例（DSLD 编号 / 产品 / 品牌） | 建议 |
| --- | --- | --- | --- |
| L-丝氨酸（L-serine） | 返回的 100 条里有 71 条含 "L-Serine"；有单一成分产品，在售 | 254751 "L-Serine"（BulkSupplements.com）；274249 "L-Serine Unflavored"（California Gold Nutrition） | 列入 |
| 辅酶 Q10（coenzyme Q10 / ubiquinone / ubiquinol） | 100 条里 97 条含该成分；有单一成分产品，在售 | 330644 "CoQ10 (Coenzyme Q10) 200mg"、330641 "Coenzyme Q10 Powder 200mg"（BulkSupplements.com） | 列入 |
| D-半乳糖（D-galactose） | **没有单一成分产品**。"galactose" 只作为复方产品的成分出现：多种维生素（如 221375 plnt "Whole Food Women's Multivitamin"）、复合酶（24530 Kirkman "Enzymaid Multi-Enzyme Complex"） | — | **待定**：按 DSLD 不能证明"可作为膳食补充剂获得" |

## 需要你决定：D-半乳糖

DSLD 只能证明 D-半乳糖出现在复方产品的标签上，不能证明有可按研究剂量（文献 1.5 g/kg/day）使用的单一成分补充剂。三个选项：

1. **不列为补充剂**：D-半乳糖按"未获批药物"处理，没有扩展使用途径就不进 3c（SLC35A2 的 D-半乳糖验收用例改为"不进 3c，记阴性证据，注明原因"）。
2. **找第二个官方来源**：例如 FDA 的 GRAS 通告库（食品成分）。如果 D-半乳糖有 GRAS 结论，可以作为"食品成分可获得"单列，报告注明"非 FDA 批准药品，作为食品成分可获得，产品质量和剂量缺乏监管"。（尚未查证。）
3. **放宽为"DSLD 中任一标签含该成分"**：不建议，复方产品里的微量成分不代表可按文献剂量获得。

建议选 2：先查 FDA GRAS 通告库；查不到就按 1 处理。
