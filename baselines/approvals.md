# Baseline approvals

2026-11-17 初始化：按用户本轮明确指示，`current/snapshot.json` 与
`historical/step3a.2-accepted/snapshot.json` 字节完全一致。
这只是历史基线的复制，**不批准当前账本中的任何变化**，没有执行升级。
历史版本覆盖现有 15 例中的 11 例，4 例 RETEST 尚未存在，明确记为缺少历史基线。

后续升级必须由用户逐条批准 diff 后执行 `scripts/promote_baseline.py`。
脚本在此追加日期、提交号、批准人、总体理由及每条变化的批准清单与理由，保留已有记录。
尚无升级记录。

## 2026-11-17 — 794f10a50930364b2358050dd1d5cf62be7bd90a

- Approver: 用户（本会话审核结论）
- Reason: 用户明确批准 A 目的规则5项、B CFTR新生儿5项、D 投票不确定性11项、E 指定结构性变化；明确拒绝C，其他待核实事项不升级。
- Previous snapshot: 2c7e28736e9d20568e689a892088c8e9b0ef3098d2680a277f5cfc679aaf48e8
- Approved candidate: eecc4996b323d65a6ff6000e85f8a54b8c42f45aa196b3664bbbbf000518b157

| Change ID | Case ID | Action | Branch | Old status | New status | Approved rationale |
| --- | --- | --- | --- | --- | --- | --- |
| 4b47d3a08124bf4b | PRAC-AGXT-c33dup | ASO exon skipping | MONDO:0009823 | not recorded (absence, not a clinical status) | not_eligible | User approval: E: later pipeline stages |
| b0da7f5d745ab485 | PRAC-AGXT-c33dup | ASO splice correction | MONDO:0009823 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 504394322edfae4a | PRAC-AGXT-c33dup | base or prime editing | MONDO:0009823 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 5213c4f25252ea08 | PRAC-AGXT-c33dup | gene replacement (AAV) | MONDO:0009823 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 2336b2332c33a4b4 | PRAC-AGXT-c33dup | RNA knockdown | MONDO:0009823 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 154bde4dba4fc585 | PRAC-AGXT-c33dup | upregulation from the normal allele | MONDO:0009823 | not recorded (absence, not a clinical status) | not_graded | User approval: E: later pipeline stages |
| a0cfd0e769811858 | PRAC-AGXT-c33dup | sodium thiosulfate (STS) | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 3e312093ebea6068 | PRAC-AGXT-c33dup | Stiripentol | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 532e8200ca32cf8d | PRAC-AGXT-c33dup | lanthanum carbonate | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 1c4a1c632af443ab | PRAC-AGXT-c33dup | bevacizumab | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 63958fa579d054f5 | PRAC-AGXT-c33dup | high oral fluid intake | MONDO:0009823 | conditional | applicable | User approval: A: purpose rule |
| 2f9ea1515fe30b42 | PRAC-AGXT-c508GA | ASO exon skipping | MONDO:0009823 | not recorded (absence, not a clinical status) | not_eligible | User approval: E: later pipeline stages |
| 6620716f183a2eb9 | PRAC-AGXT-c508GA | ASO splice correction | MONDO:0009823 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| d432551f8d57063d | PRAC-AGXT-c508GA | base or prime editing | MONDO:0009823 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 02a6dcb7831bee4d | PRAC-AGXT-c508GA | gene replacement (AAV) | MONDO:0009823 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 486529eef65d49cc | PRAC-AGXT-c508GA | RNA knockdown | MONDO:0009823 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| ee49c02680949677 | PRAC-AGXT-c508GA | upregulation from the normal allele | MONDO:0009823 | not recorded (absence, not a clinical status) | not_graded | User approval: E: later pipeline stages |
| 3a6c0980aa31d2ac | PRAC-AGXT-c508GA | sodium thiosulfate (STS) | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 359f7c56a991be4e | PRAC-AGXT-c508GA | Stiripentol | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| d0336447557fd719 | PRAC-AGXT-c508GA | lanthanum carbonate | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 7bc9e5571aa2df55 | PRAC-AGXT-c508GA | bevacizumab | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| d673ac7262539d10 | PRAC-AGXT-c508GA | high oral fluid intake | MONDO:0009823 | conditional | applicable | User approval: A: purpose rule |
| ef5e8fe1ce548305 | PRAC-ANO10 | ASO exon skipping | MONDO:0013392 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 917bec5a6463ba87 | PRAC-ANO10 | ASO splice correction | MONDO:0013392 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| a3c7222842676039 | PRAC-ANO10 | base or prime editing | MONDO:0013392 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| baf364d27472b213 | PRAC-ANO10 | gene replacement (AAV) | MONDO:0013392 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 54d48bcaa247cbec | PRAC-ANO10 | RNA knockdown | MONDO:0013392 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 8f90fddfed0025bf | PRAC-ANO10 | upregulation from the normal allele | MONDO:0013392 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 07985087c8f67a88 | PRAC-ANO10 | coenzyme Q10 | MONDO:0013392 | not recorded (absence, not a clinical status) | applicable | User approval: E: later pipeline stages |
| 86729bb46096dd38 | PRAC-CFTR-F508del | ASO exon skipping | MONDO:0009061 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| e2e5841c1e85362b | PRAC-CFTR-F508del | ASO splice correction | MONDO:0009061 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| ce5820c2c5df611d | PRAC-CFTR-F508del | base or prime editing | MONDO:0009061 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 071b84d649659499 | PRAC-CFTR-F508del | gene replacement (AAV) | MONDO:0009061 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| e3feb7611b5adffe | PRAC-CFTR-F508del | RNA knockdown | MONDO:0009061 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 6bb303d80c8340de | PRAC-CFTR-F508del | upregulation from the normal allele | MONDO:0009061 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 8f8334fe8a3c845b | PRAC-CFTR-F508del | SWEAT CF (NCT07414810) | MONDO:0009061 | conditional | not recorded (absence, not a clinical status) | User approval: E: over_cap study scope |
| a1334f38000c8e6d | PRAC-CFTR-F508del | CGMUCODIAB (NCT07851831) | MONDO:0009061 | conditional | not recorded (absence, not a clinical status) | User approval: E: over_cap study scope |
| 5c14ccde7f17917f | PRAC-CFTR-F508del | Paxlovid | MONDO:0009061 | applicable | conditional | User approval: D: context-check uncertainty |
| 2ef7a4513c893b5f | PRAC-CFTR-F508del | Dehydration | MONDO:0009061 | applicable | conditional | User approval: D: context-check uncertainty |
| 7784cb4f05e1cc50 | PRAC-CFTR-F508del | Exposure to respiratory infections | MONDO:0009061 | applicable | conditional | User approval: D: context-check uncertainty |
| 4726469a0b51d0e1 | PRAC-CFTR-F508del | tobramycin | MONDO:0009061 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 12e6e761aaa967ae | PRAC-CFTR-F508del | riociguat | MONDO:0009061 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| ad137d7eec7173cd | PRAC-CFTR-F508del | Prolastin | MONDO:0009061 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| fe3d61e88d7337d6 | PRAC-CFTR-F508del | Fat-soluble vitamin supplements | MONDO:0009061 | applicable | not_applicable | User approval: B: CFTR newborn scope |
| 2a1c23a28300c4bb | PRAC-CFTR-F508del | Nutrient-dense food & supplements | MONDO:0009061 | applicable | not_applicable | User approval: B: CFTR newborn scope |
| eba1010778f10ef8 | PRAC-CFTR-F508del | hypertonic saline | MONDO:0009061 | conditional | not recorded (absence, not a clinical status) | User approval: E: hypertonic saline key normalization |
| be6aafc92c91f023 | PRAC-CFTR-F508del | Pancreatic enzyme replacement therapy | MONDO:0009061 | applicable | not_applicable | User approval: B: CFTR newborn scope |
| d5003d7504367f92 | PRAC-CFTR-F508del | hypertonic saline | MONDO:0009061 | not recorded (absence, not a clinical status) | conditional | User approval: E: hypertonic saline key normalization |
| 92722f0b4b8eaa0f | PRAC-CFTR-F508del | contact precautions | MONDO:0009061 | conditional | not_applicable | User approval: B: CFTR newborn scope |
| f245a993cfd3c5d2 | PRAC-CFTR-F508del | Postural drainage & percussion | MONDO:0009061 | conditional | not_applicable | User approval: B: CFTR newborn scope |
| e6e1346599080989 | PRAC-COL1A1 | ASO exon skipping | MONDO:0007522 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| c3bfce7c44b798b4 | PRAC-COL1A1 | ASO exon skipping | MONDO:0020521 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 51285bcb00067def | PRAC-COL1A1 | ASO exon skipping | MONDO:0030854 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| aa13309e07022b56 | PRAC-COL1A1 | ASO splice correction | MONDO:0007522 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| c43bc9455f471f53 | PRAC-COL1A1 | ASO splice correction | MONDO:0020521 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| bb11698c141f4f05 | PRAC-COL1A1 | ASO splice correction | MONDO:0030854 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 51504fa0e1874299 | PRAC-COL1A1 | base or prime editing | MONDO:0007522 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 2fbaecb2d4c4a052 | PRAC-COL1A1 | base or prime editing | MONDO:0020521 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 7ce66adbca4ba162 | PRAC-COL1A1 | base or prime editing | MONDO:0030854 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| dac03ae9d207bdec | PRAC-COL1A1 | gene replacement (AAV) | MONDO:0007522 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 5d947e4b5a7a6e48 | PRAC-COL1A1 | gene replacement (AAV) | MONDO:0020521 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| e3db92b1f54432bf | PRAC-COL1A1 | gene replacement (AAV) | MONDO:0030854 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 8077a2ad3f95b473 | PRAC-COL1A1 | RNA knockdown | MONDO:0007522 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| d74d3c472bf9d52c | PRAC-COL1A1 | RNA knockdown | MONDO:0020521 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| e47f0f2f08acfc72 | PRAC-COL1A1 | RNA knockdown | MONDO:0030854 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 5afd6f939d1f3bb2 | PRAC-COL1A1 | upregulation from the normal allele | MONDO:0007522 | not recorded (absence, not a clinical status) | not_graded | User approval: E: later pipeline stages |
| 0caa00f8c883a254 | PRAC-COL1A1 | upregulation from the normal allele | MONDO:0020521 | not recorded (absence, not a clinical status) | not_graded | User approval: E: later pipeline stages |
| 82a0f1b5ed23fb7f | PRAC-COL1A1 | upregulation from the normal allele | MONDO:0030854 | not recorded (absence, not a clinical status) | not_graded | User approval: E: later pipeline stages |
| 43080f9a0c3ed911 | PRAC-COL1A1 | VILLAREALFC (NCT07653633) | MONDO:0007522 | conditional | not recorded (absence, not a clinical status) | User approval: E: over_cap study scope |
| 9b8a714fe6a40081 | PRAC-COL1A1 | VILLAREALFC (NCT07653633) | MONDO:0020521 | conditional | not recorded (absence, not a clinical status) | User approval: E: over_cap study scope |
| cbace548fe8b7c55 | PRAC-COL1A1 | secondhand smoke | MONDO:0030854 | applicable | conditional | User approval: D: context-check uncertainty |
| 31777137fe2d7606 | PRAC-COL1A1 | None found | MONDO:0007522 | not recorded (absence, not a clinical status) | searched_none | User approval: E: later pipeline stages |
| 987cd98ae3754a47 | PRAC-COL1A1 | None found | MONDO:0020521 | not recorded (absence, not a clinical status) | searched_none | User approval: E: later pipeline stages |
| 59d68c77c186c135 | PRAC-COL1A1 | None found | MONDO:0030854 | not recorded (absence, not a clinical status) | searched_none | User approval: E: later pipeline stages |
| a8252e687a4ea92b | PRAC-COL1A1 | bone morphogenetic protein-2 | MONDO:0030854 | applicable | conditional | User approval: D: context-check uncertainty |
| 991d89395f3607a5 | PRAC-COL1A1 | braces | MONDO:0007522 | applicable | conditional | User approval: D: context-check uncertainty |
| 2649c6fe3cdebae9 | PRAC-COL1A1 | physiotherapist | MONDO:0007522 | conditional | applicable | User approval: A: purpose rule |
| 0a8ee16c3be3d841 | PRAC-COL1A1 | physiotherapist | MONDO:0030854 | conditional | applicable | User approval: A: purpose rule |
| 3c3cc16f42c5f611 | PRAC-GRIN2B | ASO exon skipping | MONDO:0013509 | not recorded (absence, not a clinical status) | not_eligible | User approval: E: later pipeline stages |
| dc9e9521ec2b8a4f | PRAC-GRIN2B | ASO exon skipping | MONDO:0014505 | not recorded (absence, not a clinical status) | not_eligible | User approval: E: later pipeline stages |
| ebd4e999101d5ada | PRAC-GRIN2B | ASO splice correction | MONDO:0013509 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 299e2715de2c19c7 | PRAC-GRIN2B | ASO splice correction | MONDO:0014505 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 5f5b59c620060975 | PRAC-GRIN2B | base or prime editing | MONDO:0013509 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 825b08b3c927a43f | PRAC-GRIN2B | base or prime editing | MONDO:0014505 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 6fabcd537f33fe25 | PRAC-GRIN2B | gene replacement (AAV) | MONDO:0013509 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| ac17afdd9786c39f | PRAC-GRIN2B | gene replacement (AAV) | MONDO:0014505 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 786329599c10b246 | PRAC-GRIN2B | RNA knockdown | MONDO:0013509 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| f27a6b22d0078ac1 | PRAC-GRIN2B | RNA knockdown | MONDO:0014505 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 04642d7689e4c2b6 | PRAC-GRIN2B | upregulation from the normal allele | MONDO:0013509 | not recorded (absence, not a clinical status) | not_graded | User approval: E: later pipeline stages |
| 7b8871cdb27d383c | PRAC-GRIN2B | upregulation from the normal allele | MONDO:0014505 | not recorded (absence, not a clinical status) | not_graded | User approval: E: later pipeline stages |
| 09cbb35385bbd70f | PRAC-GRIN2B | NEBOGLAMINE | MONDO:0013509 | not recorded (absence, not a clinical status) | ungraded | User approval: E: later pipeline stages |
| cef09e3888318a75 | PRAC-GRIN2B | NEBOGLAMINE | MONDO:0014505 | not recorded (absence, not a clinical status) | ungraded | User approval: E: later pipeline stages |
| cb514e0b6e0f12ca | PRAC-GRIN2B | RAPASTINEL | MONDO:0013509 | not recorded (absence, not a clinical status) | ungraded | User approval: E: later pipeline stages |
| 28219f8f7395db88 | PRAC-GRIN2B | RAPASTINEL | MONDO:0014505 | not recorded (absence, not a clinical status) | ungraded | User approval: E: later pipeline stages |
| f97104ed2e4e4960 | PRAC-GRIN2B | APIMOSTINEL | MONDO:0013509 | not recorded (absence, not a clinical status) | ungraded | User approval: E: later pipeline stages |
| 1880927211cb2ea1 | PRAC-GRIN2B | APIMOSTINEL | MONDO:0014505 | not recorded (absence, not a clinical status) | ungraded | User approval: E: later pipeline stages |
| c53bed624b4a6aed | PRAC-GRIN2B | memantine | MONDO:0014505 | not recorded (absence, not a clinical status) | applicable | User approval: E: later pipeline stages |
| 71301c19501e9f38 | PRAC-GRIN2B | L-serine | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| b85f1ae575fb6a5d | PRAC-GRIN2B | None found | MONDO:0013509 | not recorded (absence, not a clinical status) | searched_none | User approval: E: later pipeline stages |
| cd3826594a158155 | PRAC-KMT2B | ASO exon skipping | MONDO:0015004 | not recorded (absence, not a clinical status) | not_eligible | User approval: E: later pipeline stages |
| 0f1661eacaa73a9c | PRAC-KMT2B | ASO splice correction | MONDO:0015004 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| c479f7818b86ab45 | PRAC-KMT2B | base or prime editing | MONDO:0015004 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 0173712e40fd4dc6 | PRAC-KMT2B | gene replacement (AAV) | MONDO:0015004 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| b908249cded8cd9e | PRAC-KMT2B | RNA knockdown | MONDO:0015004 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| d50090fae835e401 | PRAC-KMT2B | upregulation from the normal allele | MONDO:0015004 | not recorded (absence, not a clinical status) | not_graded | User approval: E: later pipeline stages |
| f0bfe757bcb4729f | PRAC-KMT2B | None found | MONDO:0015004 | not recorded (absence, not a clinical status) | searched_none | User approval: E: later pipeline stages |
| 24e06489dbf9c904 | PRAC-KMT2B | benzodiazepines | MONDO:0015004 | applicable | conditional | User approval: D: context-check uncertainty |
| 82eec1c31bba7fc9 | PRAC-KMT2B | trihexiphenidyl | MONDO:0015004 | applicable | conditional | User approval: D: context-check uncertainty |
| 17027f2c99998df9 | PRAC-KMT2B | tetrabenazine | MONDO:0015004 | applicable | conditional | User approval: D: context-check uncertainty |
| c45efee4064db36e | PRAC-KMT2B | levodopa | MONDO:0015004 | applicable | conditional | User approval: D: context-check uncertainty |
| 809702a5c2bdf199 | PRAC-NF1 | ASO exon skipping | MONDO:0018975 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| ed08d88063a50989 | PRAC-NF1 | ASO splice correction | MONDO:0018975 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 7c66a342415d0710 | PRAC-NF1 | base or prime editing | MONDO:0018975 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 4437b9c8f573647b | PRAC-NF1 | gene replacement (AAV) | MONDO:0018975 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 947e94b19e3703c9 | PRAC-NF1 | RNA knockdown | MONDO:0018975 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| ada73ed0b7f2f23b | PRAC-NF1 | upregulation from the normal allele | MONDO:0018975 | not recorded (absence, not a clinical status) | not_graded | User approval: E: later pipeline stages |
| a47900ff176888ba | PRAC-NF1 | vitamin D(3) ointment | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| c07417edc16fa74d | PRAC-NF1 | thalidomide | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| c70d5b49671d2a38 | PRAC-NF1 | regorafenib | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 4a5ede70357d3d87 | PRAC-NF1 | cabozantinib | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 4b3a6aa3fd1aefc5 | PRAC-NF1 | everolimus | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| ce59e9c4e0b2f04f | PRAC-NF1 | trametinib | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| d8e57a2ce315fd9c | PRAC-NF1 | pirfenidone | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 4d03a1a2c928ab6c | PRAC-NF1 | Pexidartinib | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 9759b3e98d964062 | PRAC-NF1 | curcumin | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| a41a0380fdc7ea65 | PRAC-NF1 | sirolimus | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 57b23da58dfcebb5 | PRAC-NF1 | lovastatin | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| a01f4a03e09b3499 | PRAC-NF1 | risedronate sodium | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| cda0a1aed9154b9a | PRAC-OTC | ASO exon skipping | MONDO:0010703 | not recorded (absence, not a clinical status) | not_eligible | User approval: E: later pipeline stages |
| 9532b8c8e3d4e387 | PRAC-OTC | ASO splice correction | MONDO:0010703 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 082552ee388b2e9f | PRAC-OTC | base or prime editing | MONDO:0010703 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| dd79480b22686ab2 | PRAC-OTC | gene replacement (AAV) | MONDO:0010703 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| f836c0ed76ef2180 | PRAC-OTC | RNA knockdown | MONDO:0010703 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 129d443b2eadfabb | PRAC-OTC | upregulation from the normal allele | MONDO:0010703 | not recorded (absence, not a clinical status) | not_graded | User approval: E: later pipeline stages |
| 6bbd71d4216580fa | PRAC-OTC | Haloperidol | MONDO:0010703 | applicable | conditional | User approval: D: context-check uncertainty |
| 0348ada4af4f3f86 | PRAC-OTC | None found | MONDO:0010703 | not recorded (absence, not a clinical status) | searched_none | User approval: E: later pipeline stages |
| 588ee00f7ec729a8 | PRAC-OTC | nitrogen-scavenging drugs | MONDO:0010703 | conditional | applicable | User approval: A: purpose rule |
| 9aa66dd93592b1b5 | PRAC-SLC35A2-ex7 | ASO exon skipping | MONDO:0010478 | not recorded (absence, not a clinical status) | not_eligible | User approval: E: later pipeline stages |
| 6a81a54f107d98fe | PRAC-SLC35A2-ex7 | ASO splice correction | MONDO:0010478 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 476b35ef05928076 | PRAC-SLC35A2-ex7 | base or prime editing | MONDO:0010478 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| 31ef5a70f6dc5cc9 | PRAC-SLC35A2-ex7 | gene replacement (AAV) | MONDO:0010478 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 5edd7253dea1fff9 | PRAC-SLC35A2-ex7 | RNA knockdown | MONDO:0010478 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| b1031e7154a2a849 | PRAC-SLC35A2-ex7 | upregulation from the normal allele | MONDO:0010478 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 0ab75106ffd83b16 | PRAC-SLC35A2-ex7 | D-galactose | MONDO:0010478 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
| 8111a23c95a2e4ec | PRAC-SLC35A2-ex8 | ASO exon skipping | MONDO:0010478 | not recorded (absence, not a clinical status) | not_eligible | User approval: E: later pipeline stages |
| e50a0cf990e50bd6 | PRAC-SLC35A2-ex8 | ASO splice correction | MONDO:0010478 | not recorded (absence, not a clinical status) | not_applicable | User approval: E: later pipeline stages |
| 1403befecb4f62f5 | PRAC-SLC35A2-ex8 | base or prime editing | MONDO:0010478 | not recorded (absence, not a clinical status) | theoretically_possible | User approval: E: later pipeline stages |
| f65775b5045911de | PRAC-SLC35A2-ex8 | gene replacement (AAV) | MONDO:0010478 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 3d3568e31b169f66 | PRAC-SLC35A2-ex8 | RNA knockdown | MONDO:0010478 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 023542a81ae116ac | PRAC-SLC35A2-ex8 | upregulation from the normal allele | MONDO:0010478 | not recorded (absence, not a clinical status) | unable_to_assess | User approval: E: later pipeline stages |
| 10d478582ec38eb1 | PRAC-SLC35A2-ex8 | D-galactose | MONDO:0010478 | not recorded (absence, not a clinical status) | conditional | User approval: E: later pipeline stages |
