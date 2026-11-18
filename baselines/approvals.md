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

## 2026-11-17 — 26a54c580cdd5daea621463a71ba1828b367d02d

- Approver: 用户（本会话 COL1A1 physiotherapist 两分支更正批准）
- Reason: 用户明确撤销此前 physiotherapist 只改文字不改状态的个案要求：旧 applicable 依赖孕期段落，对本病人无效；以普通来源核查 conditional 为准。批准两个诊断分支降为 conditional，reason 写明普通 NBK1295 段落对相应诊断分支的适用范围尚未确认。仅升级这两行，其他 C、61项证据细节与 RETEST 首个基线不在本次批准内。
- Previous snapshot: eecc4996b323d65a6ff6000e85f8a54b8c42f45aa196b3664bbbbf000518b157
- Approved candidate: 43f31989324640be76d7df8589b2592b90a4ffd698bbd1765429a789011fb4a3

| Change ID | Case ID | Action | Branch | Old status | New status | Approved rationale |
| --- | --- | --- | --- | --- | --- | --- |
| 6f96422a8c74556d | PRAC-COL1A1 | physiotherapist | MONDO:0007522 | applicable | conditional | 用户明确撤销此前 physiotherapist 只改文字不改状态的个案要求：旧 applicable 依赖孕期段落，对本病人无效；以普通来源核查 conditional 为准。批准两个诊断分支降为 conditional，reason 写明普通 NBK1295 段落对相应诊断分支的适用范围尚未确认。仅升级这两行，其他 C、61项证据细节与 RETEST 首个基线不在本次批准内。 |
| 12bbbb9d9948ba97 | PRAC-COL1A1 | physiotherapist | MONDO:0030854 | applicable | conditional | 用户明确撤销此前 physiotherapist 只改文字不改状态的个案要求：旧 applicable 依赖孕期段落，对本病人无效；以普通来源核查 conditional 为准。批准两个诊断分支降为 conditional，reason 写明普通 NBK1295 段落对相应诊断分支的适用范围尚未确认。仅升级这两行，其他 C、61项证据细节与 RETEST 首个基线不在本次批准内。 |

## 2026-11-17 — b0e3ef38584c82d00e62b3c43c8be9aa3012b055

- Approver: 用户（本会话第五轮第2、4项）
- Reason: 用户第五轮明确：D组已批准braces×3，补升此前错误按投票分歧筛选而漏掉的ring splints及wrist/thumb braces两项；同时明确批准删除历史已not_applicable的NCT01822834成人登记和NCT07513051新生儿试验。仅此四项，不批准其余噪音清单或RETEST首个基线。
- Previous snapshot: 43f31989324640be76d7df8589b2592b90a4ffd698bbd1765429a789011fb4a3
- Approved candidate: cf749076cd16224e7a6c25624b31604e47761d4e463cb71fea5590a44e6e727f

| Change ID | Case ID | Action | Branch | Old status | New status | Approved rationale |
| --- | --- | --- | --- | --- | --- | --- |
| 0c4515fea42d3927 | PRAC-CFTR-F508del | Bronchiectasis and NTM Research Registry (NCT01822834) | MONDO:0009061 | not_applicable | not recorded (absence, not a clinical status) | 用户批准删除：历史状态已为not_applicable，年龄不符且非CFTR召回缺口；不产生新排除。 |
| c17368df08086084 | PRAC-CFTR-F508del | DIaphragmatic Swing According to Cpap Flow Output in NEOnates (DISCONEO) (NCT07513051) | MONDO:0009061 | not_applicable | not recorded (absence, not a clinical status) | 用户批准删除：历史状态已为not_applicable，年龄不符且非CFTR召回缺口；不产生新排除。 |
| 4d9bbe81542ddc92 | PRAC-COL1A1 | ring splints | MONDO:0007522 | applicable | conditional | D组braces×3批准漏升补正；HPO未知保持conditional，不改判定代码或正式账本状态。 |
| a4389c851d9c8674 | PRAC-COL1A1 | wrist or wrist & thumb braces | MONDO:0007522 | applicable | conditional | D组braces×3批准漏升补正；HPO未知保持conditional，不改判定代码或正式账本状态。 |

## 2026-11-17 — b809283644d1aa096484acf26e87191bfc4d8cf6

- Approver: 用户（本次审核第1、2项）
- Reason: 明确批准155项分组候选，另批准AGXT RKSC/ProRKS及CFTR STOP PEDS/瑜伽6个行动×分支；COL1A1 EDS18项暂缓，其他C与RETEST不升级。
- Previous snapshot: cf749076cd16224e7a6c25624b31604e47761d4e463cb71fea5590a44e6e727f
- Approved candidate: 4ca175bae9e7b8608ab62e2b7898621331283705f26762fab76aa727ebfbdca4

| Change ID | Case ID | Action | Branch | Old status | New status | Approved rationale |
| --- | --- | --- | --- | --- | --- | --- |
| f9622032bf3b5584 | PRAC-AGXT-c33dup | RKSC (NCT00588562) | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| fb886e84217df4db | PRAC-AGXT-c33dup | Rare Kidney Stone Consortium Biobank (NCT02026388) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 6f3446215cb53e61 | PRAC-AGXT-c33dup | ProRKS (NCT02780297) | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 38693a830a5a47e6 | PRAC-AGXT-c33dup | PHYOX7 (NCT04580420) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| ee33b34ac26af907 | PRAC-AGXT-c33dup | DAILY-LUMA (NCT06225882) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 4a4b2a4746dba8ac | PRAC-AGXT-c33dup | CRYSTAL (NCT06465472) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 0e2746a0dc08ac99 | PRAC-AGXT-c33dup | Clinical Exploration Study of YOLT-203 in the Treatment of Type 1 Primary Hyperoxaluria (PH1) (NCT06511349) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| d29f7c2807172323 | PRAC-AGXT-c33dup | Phase 1/2 Study of ABO-101 in Primary Hyperoxaluria Type 1 (redePHine) (NCT06839235) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 289a9badd2787599 | PRAC-AGXT-c33dup | Study of YOLT-203 in Children and Adults With Primary Hyperoxaluria Type 1 (PH1) (NCT07587021) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| b04275addd9dba51 | PRAC-AGXT-c33dup | Phase I Exploratory Study of YOLT-203 in Patients With Primary Hyperoxaluria Type 1 (PH1) (NCT07776626) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 2a364f88dffb552c | PRAC-AGXT-c33dup | liver transplant | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| b9b61ff384279f3d | PRAC-AGXT-c33dup | adequate fluid intake | MONDO:0009823 | not_applicable | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 52ab9adfea7572f4 | PRAC-AGXT-c33dup | pyrophosphate-containing solutions | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 35082c7626cdff51 | PRAC-AGXT-c33dup | potassium citrate | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| aee81bde01f5f829 | PRAC-AGXT-c33dup | sodium citrate | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 0c620cf2dba8e5aa | PRAC-AGXT-c33dup | dialysis | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| c3b5002b476ca207 | PRAC-AGXT-c33dup | intravenous fluid administration | MONDO:0009823 | not_applicable | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 697ea6089588ecad | PRAC-AGXT-c33dup | shockwave lithotripsy | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 904f9ab49bd9cdd2 | PRAC-AGXT-c508GA | RKSC (NCT00588562) | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 3d0d87e9b5d0229f | PRAC-AGXT-c508GA | Rare Kidney Stone Consortium Biobank (NCT02026388) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| b2017b1f265c1d7f | PRAC-AGXT-c508GA | ProRKS (NCT02780297) | MONDO:0009823 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| c2486eb39a7d74b5 | PRAC-AGXT-c508GA | PHYOX7 (NCT04580420) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 19cb2e0f459f3093 | PRAC-AGXT-c508GA | DAILY-LUMA (NCT06225882) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 13faa77e7f4dbf83 | PRAC-AGXT-c508GA | CRYSTAL (NCT06465472) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 539461a5f1af4161 | PRAC-AGXT-c508GA | Clinical Exploration Study of YOLT-203 in the Treatment of Type 1 Primary Hyperoxaluria (PH1) (NCT06511349) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| f3dfcb4982c90071 | PRAC-AGXT-c508GA | Phase 1/2 Study of ABO-101 in Primary Hyperoxaluria Type 1 (redePHine) (NCT06839235) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| a01f90935389d51f | PRAC-AGXT-c508GA | Study of YOLT-203 in Children and Adults With Primary Hyperoxaluria Type 1 (PH1) (NCT07587021) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| c999298f25c8b522 | PRAC-AGXT-c508GA | Phase I Exploratory Study of YOLT-203 in Patients With Primary Hyperoxaluria Type 1 (PH1) (NCT07776626) | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| e32309a713e05687 | PRAC-AGXT-c508GA | liver transplant | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 379fb54b5f5855a3 | PRAC-AGXT-c508GA | adequate fluid intake | MONDO:0009823 | conditional | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 3d997ed0b97c2574 | PRAC-AGXT-c508GA | pyrophosphate-containing solutions | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| c19c73d85ec24b6c | PRAC-AGXT-c508GA | potassium citrate | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 6f62538c379b752f | PRAC-AGXT-c508GA | sodium citrate | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 965ef34399a142b5 | PRAC-AGXT-c508GA | dialysis | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| f2c4d9d476851489 | PRAC-AGXT-c508GA | intravenous fluid administration | MONDO:0009823 | conditional | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 28b89e630cb11892 | PRAC-AGXT-c508GA | shockwave lithotripsy | MONDO:0009823 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 5366172274fb5d99 | PRAC-ANO10 | None found | MONDO:0013392 | not recorded (absence, not a clinical status) | searched_none | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 993a1d48e8bcb3ca | PRAC-ANO10 | None found | MONDO:0013392 | not recorded (absence, not a clinical status) | searched_none | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| f304cd04284e5f38 | PRAC-ANO10 | None found | MONDO:0013392 | not recorded (absence, not a clinical status) | searched_none | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 741e6cd68df0a8a2 | PRAC-ANO10 | modify food consistency | MONDO:0013392 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 3c241c8d1d313c77 | PRAC-ANO10 | nutritional & vitamin supplementation | MONDO:0013392 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| b8e2158c3aef61dd | PRAC-ANO10 | weight control | MONDO:0013392 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 413628fef93061d0 | PRAC-ANO10 | baclofen | MONDO:0013392 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| c80f380c6ebd7b05 | PRAC-ANO10 | dantrolene | MONDO:0013392 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 3cd3fffb0c9e9d2f | PRAC-ANO10 | riluzole | MONDO:0013392 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| ebc212b83b835fb5 | PRAC-ANO10 | tizanidine | MONDO:0013392 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 6790dfb19a9814a2 | PRAC-ANO10 | surgical treatment | MONDO:0013392 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| eedb60394f742f36 | PRAC-ANO10 | transcranial magnetic stimulation | MONDO:0013392 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| bcfabfe63238734a | PRAC-ANO10 | adaptive devices | MONDO:0013392 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 9f3c3e8dbce28b8d | PRAC-ANO10 | alternative communication methods | MONDO:0013392 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 5c00b4ab998838cc | PRAC-ANO10 | home adaptations | MONDO:0013392 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| a584e0c1675c0301 | PRAC-ANO10 | occupational therapy | MONDO:0013392 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| f821e921c1f5734f | PRAC-ANO10 | physical therapy | MONDO:0013392 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 99e09baf5e1c2371 | PRAC-ANO10 | speech-language therapy | MONDO:0013392 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 7d4b78e893b47b4a | PRAC-CFTR-F508del | Personalized Theratyping Trial (NCT03587961) | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 95edd1d01f982efd | PRAC-CFTR-F508del | STOP360AG (NCT05548283) | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 466187fdd481fe4f | PRAC-CFTR-F508del | Regional Monitoring of CF Lung Disease (NCT06339593) | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 3303e97b1554a5c3 | PRAC-CFTR-F508del | Targeting Inflammation With Losartan to Improve Response to Modulator Therapy in Cystic Fibrosis. (NCT06364176) | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| e4db6afbe941bbe9 | PRAC-CFTR-F508del | STOP PEDS RCT (NCT06654752) | MONDO:0009061 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 5b0a73880315306f | PRAC-CFTR-F508del | ENACT (NCT07148739) | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| edd8f510fc683334 | PRAC-CFTR-F508del | Safety and Efficacy of Inhaled BMD003 (CFTR mRNA) in Chinese Cystic Fibrosis Patients Aged ≥12 Years (NCT07485543) | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 00078e7d0ef091a7 | PRAC-CFTR-F508del | Pharmacokinetics of Elexacaftor/Tezacaftor/Ivacaftor in Cystic Fibrosis (NCT07809867) | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 75642a1239a8a79f | PRAC-CFTR-F508del | Diagnostic Value of Oropharyngeal Suction and Effect of Respiratory Physiotherapy on the Detection of Microorganisms in the Pediatric Patient (NCT07903792) | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| b69bcedb0b2d3778 | PRAC-CFTR-F508del | The Effects of Yoga Practice on Exercise Capacity, Arterial Stiffness, Respiratory Function, Peripheral Muscle Strength, Posture and Quality of Life in Children With Cystic Fibrosis (NCT07930221) | MONDO:0009061 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 1456a0d4188418f8 | PRAC-CFTR-F508del | aerosolized antibiotic | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| fe7a05cb63ae5b8e | PRAC-CFTR-F508del | bronchodilator | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 080488172d59fc57 | PRAC-CFTR-F508del | fat-soluble vitamin A supplementation | MONDO:0009061 | not_applicable | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 535195420e5579dc | PRAC-CFTR-F508del | folate supplementation | MONDO:0009061 | not_applicable | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| c984456d181d80c0 | PRAC-CFTR-F508del | Gonadotropin ovulation induction | MONDO:0009061 | not_applicable | not_applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 7c2089d4166fd1bc | PRAC-CFTR-F508del | iron supplementation | MONDO:0009061 | not_applicable | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| eca8410a75cd7246 | PRAC-CFTR-F508del | laxative treatment | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 8d3ff0b246f0f547 | PRAC-CFTR-F508del | insulin | MONDO:0009061 | not_applicable | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| c282e26f69a28b16 | PRAC-CFTR-F508del | airway clearance | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 4ed873fe2f88eb6a | PRAC-CFTR-F508del | airway clearance practices | MONDO:0009061 | not_applicable | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 709dbdd505b3f7d8 | PRAC-CFTR-F508del | Intrauterine insemination | MONDO:0009061 | not_applicable | not_applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| f5a9b68f5f9296cd | PRAC-CFTR-F508del | IVF | MONDO:0009061 | not_applicable | not_applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 4a11c962f2f88402 | PRAC-CFTR-F508del | surgical intervention for nasal/sinus symptoms | MONDO:0009061 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| c7041a954c71ca40 | PRAC-COL1A1 | Preliminary Evaluation of the Safety and Tolerability of SPOT-mRNA01 Subcutaneously Administered in Healthy Subjects (NCT06567119) | MONDO:0007522 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 03f93b0cf0af7f4c | PRAC-COL1A1 | Preliminary Evaluation of the Safety and Tolerability of SPOT-mRNA01 Subcutaneously Administered in Healthy Subjects (NCT06567119) | MONDO:0020521 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 173d203ec1b7db32 | PRAC-COL1A1 | Preliminary Evaluation of the Safety and Tolerability of SPOT-mRNA01 Subcutaneously Administered in Healthy Subjects (NCT06567119) | MONDO:0030854 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 40c02dad1d652594 | PRAC-COL1A1 | VILLAREALFC (NCT07653633) | MONDO:0030854 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 06f8f5c4ed2cbd8d | PRAC-COL1A1 | tranexamic acid | MONDO:0007522 | conditional | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| b0f4073d93f7bc12 | PRAC-COL1A1 | oxytocin | MONDO:0007522 | conditional | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 77eb4735695ad72d | PRAC-COL1A1 | alternating positions | MONDO:0030854 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| a30c08add1998ca3 | PRAC-COL1A1 | cesarean section | MONDO:0030854 | conditional | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| f1630a07822caef4 | PRAC-COL1A1 | episiotomy | MONDO:0007522 | conditional | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 47786087bd16f68c | PRAC-COL1A1 | occupational therapy | MONDO:0030854 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| fb5f514f2b8c4a61 | PRAC-GRIN2B | Online Study of People Who Have Genetic Changes and Features of Autism: Simons Searchlight (NCT01238250) | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| ab1c286cf990ed01 | PRAC-GRIN2B | Open-label, Single-arm Trial of Ganaxolone in CDD Patients 6 Months to Less Than 2 Years Old (NCT05249556) | MONDO:0014505 | not recorded (absence, not a clinical status) | not_applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 69f765836a08cb7a | PRAC-GRIN2B | ENDEAVOR (NCT05419492) | MONDO:0014505 | not recorded (absence, not a clinical status) | not_applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 72753fc03f6bd8f5 | PRAC-GRIN2B | A Natural History Study Seeks to Understand the Clinical, Genomic, Pharmacological, Laboratory, and Dietary Determinates of Pyrimidine and Purine Metabolism Disorders (NCT06092346) | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| d785606a4ce5a37a | PRAC-GRIN2B | DEE-RETRO (NCT06380192) | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| b6d21abd46546d61 | PRAC-GRIN2B | Beeline: A Phase 3 Study in GRIN-related Neurodevelopmental Disorder (NCT07224581) | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 2623a3e4820f4c5d | PRAC-GRIN2B | Beeline: A Phase 3 Study in GRIN-related Neurodevelopmental Disorder (NCT07224581) | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| bd7adcabeab04295 | PRAC-GRIN2B | TAP-GRIN: Interventional Study on Patients With GRIN-related Neurodevelopmental Disorders (NCT07377032) | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 555f420a79938136 | PRAC-GRIN2B | TAP-GRIN: Interventional Study on Patients With GRIN-related Neurodevelopmental Disorders (NCT07377032) | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| c167289982634d9d | PRAC-GRIN2B | A Study to Evaluate the Safety and Pharmacokinetics of RC001 in Children With Dravet Syndrome (NCT07675746) | MONDO:0014505 | not recorded (absence, not a clinical status) | not_applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 0dfbb4da4bd16873 | PRAC-GRIN2B | A Study to Evaluate the Safety and Efficacy of CBD-OS in Participants With DEE (NCT07723976) | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 67588e4672dd8fc7 | PRAC-GRIN2B | A Fully Remote Feasibility Trial of Phenylbutyrate for SLC6A1-Related Disorders (NCT07847918) | MONDO:0014505 | not recorded (absence, not a clinical status) | not_applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 99b7dc1c2fd82246 | PRAC-GRIN2B | IMPACT-Ready Study (NCT07931690) | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 7bfe4c5d69ff210d | PRAC-GRIN2B | IMPACT-Ready Study (NCT07931690) | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| ffe2ba2244db3a29 | PRAC-GRIN2B | None found | MONDO:0013509 | not recorded (absence, not a clinical status) | searched_none | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| fb50fc0cd49ecec0 | PRAC-GRIN2B | None found | MONDO:0014505 | not recorded (absence, not a clinical status) | searched_none | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| bf0334a99a75e697 | PRAC-GRIN2B | None found | MONDO:0013509 | not recorded (absence, not a clinical status) | searched_none | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| ea6dda13d716191a | PRAC-GRIN2B | None found | MONDO:0014505 | not recorded (absence, not a clinical status) | searched_none | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| dbd0cb993a74fccd | PRAC-GRIN2B | anti-seizure medication | MONDO:0013509 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 69c7de54bb33e0cc | PRAC-GRIN2B | anti-seizure medication | MONDO:0014505 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 88d0668b6a3813d5 | PRAC-GRIN2B | durable medical equipment | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| baabf2ab318695d6 | PRAC-GRIN2B | durable medical equipment | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 2635a30b136c7d3c | PRAC-GRIN2B | early intervention program | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| d72488209163b587 | PRAC-GRIN2B | early intervention program | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| ad59523409cd808f | PRAC-GRIN2B | feeding therapy | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 79247702c43edc4d | PRAC-GRIN2B | feeding therapy | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 5c3c93f73e2f96bf | PRAC-GRIN2B | occupational therapy | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| f57460b7f26f68ce | PRAC-GRIN2B | occupational therapy | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 7d2158b682c6a1fa | PRAC-GRIN2B | developmental preschool | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 54251b778463a852 | PRAC-GRIN2B | developmental preschool | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| fccfed56b947196e | PRAC-GRIN2B | physical therapy | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| d5bd339bb981894f | PRAC-GRIN2B | physical therapy | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| cd039f7d0437512b | PRAC-GRIN2B | speech therapy | MONDO:0013509 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 2d68cd8cb9a86f78 | PRAC-GRIN2B | speech therapy | MONDO:0014505 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 087ce957dffa8276 | PRAC-KMT2B | None found | MONDO:0015004 | searched_none | searched_none | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| c2afd8103740bb83 | PRAC-NF1 | Cyclin-Dependent Kinase (CDK)4/6 Inhibitor Abemaciclib for Neurofibromatosis Type I (NF1) Related Atypical Neurofibromas (NCT04750928) | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 85a8c8880e7c5893 | PRAC-NF1 | Identification of Pre-Malignant Lesions In Pediatric Patients With Neurofibromatosis Type 1 Using Novel Magnetic Resonance Imaging Techniques Paired With Artificial Intelligence (NCT04763109) | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| bb9d4b67ffe375b9 | PRAC-NF1 | A Study to Evaluate the Feasibility of a Physiologic Biomarker to Assess Pain and Other Sensory Problems Using Pupillometry in Participants With Neurofibromatosis Type 1 (NF1) (NCT06507748) | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| fb54e8e297dec108 | PRAC-NF1 | INSPIRE-NF1 (NCT06541847) | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| db01af6b5f60b43b | PRAC-NF1 | Clinical Study on the Treatment of Type I Neurofibromatosis With Smeitinib Hydrosulfate Capsule (NCT06620354) | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 50b65292b8a41a89 | PRAC-NF1 | The Clinical Study of the Treatment of Patients With Type I Neurofibromatosis With Smetinib Hydrosulfate Capsule (NCT06621082) | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 4c347f656c33ba0f | PRAC-NF1 | iCanCope With NF: Innovating an Efficacious Digital Self-management and Transitional Care Program for Adolescents With Neurofibromatosis (NCT07077408) | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| ec11d579e5b1220b | PRAC-NF1 | Tailoring an Online Platform to Promote Evidence-Based Care for Adults With Neurofibromatosis 1 and Low Health Literacy (NCT07233408) | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 4f9690c07e0d2963 | PRAC-NF1 | NF118 (NCT07521657) | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 9d70be6b001119fd | PRAC-NF1 | A Study of Mirdametinib in Infants and Toddlers With Neurofibromatosis Type 1 Associated Plexiform Neurofibromas (NCT07850635) | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| e56bf587616b6709 | PRAC-NF1 | radiotherapy | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| a709a06cf63b1142 | PRAC-NF1 | selumetinib | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 34a4968d17e10172 | PRAC-NF1 | mirdametinib | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 874f37ff6cf1395d | PRAC-NF1 | bisphosphonate | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| e4a912206887a17a | PRAC-NF1 | MEK inhibitors | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| ba80f012d61b1e8c | PRAC-NF1 | Vitamin D | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| df23f7ad2f7858b5 | PRAC-NF1 | calcium | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 2be2e67dccc007c5 | PRAC-NF1 | methylphenidate | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| fefc4854eb3a5eb0 | PRAC-NF1 | complete surgical excision | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 178e5011df1cda51 | PRAC-NF1 | electrocautery | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 70c1ab8f3b30bb1c | PRAC-NF1 | laser | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| f939f91a079e375f | PRAC-NF1 | radiotherapy | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| e4180c92ac9e19ef | PRAC-NF1 | surgical management | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 292ff90857b6382f | PRAC-NF1 | surgical removal | MONDO:0018975 | not recorded (absence, not a clinical status) | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 14cee1c876dcda7b | PRAC-OTC | intact versus essential amino acid supplementation | MONDO:0010703 | not_applicable | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 9ba015865d5289a8 | PRAC-OTC | low-protein diet | MONDO:0010703 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| cb4406e5168da2c1 | PRAC-OTC | lipid emulsion | MONDO:0010703 | not_applicable | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 723e5776ffadd48b | PRAC-OTC | dextrose | MONDO:0010703 | not_applicable | not recorded (absence, not a clinical status) | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 98d38d2d0f999e48 | PRAC-OTC | CKRT | MONDO:0010703 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| a1b8fae9420dfc18 | PRAC-OTC | CVVHD | MONDO:0010703 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 0e13577b063def49 | PRAC-OTC | high-dose CKRT | MONDO:0010703 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 4ad249d6912da64e | PRAC-OTC | intermittent HD | MONDO:0010703 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 05a3bdef1e6ec124 | PRAC-OTC | renal replacement therapy | MONDO:0010703 | conditional | conditional | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 8baf57c221a9d2ee | PRAC-SLC35A2-ex7 | preschool education services in the least restrictive environment | MONDO:0010478 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 2cfd3b3cf1584e2c | PRAC-SLC35A2-ex7 | start early intervention as soon as the delay is recognized | MONDO:0010478 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 800fa316a313d3b2 | PRAC-SLC35A2-ex7 | multidisciplinary developmental intervention team (developmental paediatrics or paediatric neurology, clinical psychology, occupational therapy, physiotherapy, special education, speech therapy) | MONDO:0010478 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 477249fa33a5b3a0 | PRAC-SLC35A2-ex8 | preschool education services in the least restrictive environment | MONDO:0010478 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 9f3242ec879c5623 | PRAC-SLC35A2-ex8 | start early intervention as soon as the delay is recognized | MONDO:0010478 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
| 53e356384cb67118 | PRAC-SLC35A2-ex8 | multidisciplinary developmental intervention team (developmental paediatrics or paediatric neurology, clinical psychology, occupational therapy, physiotherapy, special education, speech therapy) | MONDO:0010478 | not recorded (absence, not a clinical status) | applicable | 用户明确批准155项分组或AGXT/CFTR试验新增；不含COL1A1 EDS18项。 |
