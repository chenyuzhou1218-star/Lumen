# 评测结果：2026-10-25-after-review

模型：脚本模型（bench/policies.py），没有调用任何真实模型

## 记忆召回

| 配置 | recall@8 | MRR | 未警示的不可信笔记 | 不可信笔记排在正确笔记前 | 越权可见 | 全对的问题 |
|---|---|---|---|---|---|---|
| ADR 0003（本批之前） | 0.909 | 0.649 | 3 | 1 | 0 | 5/11 |
| +M1 主张状态 | 0.909 | 0.635 | 3 | 2 | 0 | 5/11 |
| +M3 按主张拆分 | 1.000 | 0.703 | 3 | 2 | 0 | 5/11 |
| +M2 耦合回忆（当前） | 1.000 | 0.761 | 3 | 3 | 0 | 6/11 |
| +M6 按意思回忆 | 未评测：没有指定嵌入模型（用 --embedding-config 指向你的配置文件） | | | | | |

### shop-history：逐题（+M2 耦合回忆（当前））

| 问题 | 语言 | recall | RR | 未警示 | 排在前 | 前 5 条 |
|---|---|---|---|---|---|---|
| p1 玩家说断线重连之后比赛奖励到账了两次，怎么回事？ | zh | 1.000 | 1.000 | 1 | 0 | claim:c3, claim:c1, summary:t2⚠, note:n13, claim:c2⚠ |
| p2 ShopUI.onBuyClick 点一次扣了两次钱 | zh | 1.000 | 1.000 | 0 | 0 | claim:c1, claim:c6⚠, summary:t1 |
| p3 金币和 ledger 流水对不上 | zh | 1.000 | 1.000 | 0 | 0 | claim:c4, note:n10, claim:c5, note:n4, claim:c3 |
| p4 点购买没反应，也没有任何提示 | zh | 1.000 | 0.500 | 0 | 0 | note:n1, summary:t4⚠, claim:c6⚠ |
| p5 金币显示不刷新 | zh | 1.000 | 1.000 | 0 | 0 | note:n1, summary:t1 |
| p6 add_gold 要不要加 request_id 幂等键？ | zh | 1.000 | 1.000 | 0 | 0 | note:n4, claim:c3, summary:t1, claim:c5, claim:c4 |
| p7 spend_gold 并发购买怎么测试 | zh | 1.000 | 1.000 | 0 | 0 | claim:c5, claim:c4, claim:c3, claim:c6⚠, summary:t1 |
| p8 Why does /api/session/reconnect change the player's gold? | en | 1.000 | 0.333 | 0 | 0 | claim:c5, claim:c4, claim:c3, note:n4, claim:c1 |
| p9 match reward paid twice | en | 1.000 | 0.200 | 1 | 1 | note:n10, note:n9, note:n2, note:n13, summary:t2⚠ |
| p10 retryFetch | code | 1.000 | 1.000 | 0 | 0 | claim:c1, summary:t1, claim:c6⚠ |
| p11 web/match.js 的 finishMatch 有什么已知问题？ | zh | 1.000 | 0.333 | 1 | 2 | note:n13, claim:c2⚠, note:n2, note:n4, claim:c3 |

## 推理：图谱分析（无模型）

- shop-static：缺陷检出 7/7，平均排名 5.140（共报告 11 条风险，其中 7 条对应已知缺陷）；共同根因第 1 名命中 2/3；影响范围召回 1.000

| 缺陷 | 检出 | 排名 |
|---|---|---|
| d1 player.gold 被三个入口写入，没有锁也没有事务 | 是 | 5 |
| d2 reconnect 重放 settle，add_gold 没有幂等键 | 是 | 2 |
| d3 retryFetch 重试购买，buy 没有幂等键 | 是 | 1 |
| d4 spend_gold 写 players 和 ledger 没有事务 | 是 | 4 |
| d5 spend_gold 返回 None，buy 把它变成 200 {} | 是 | 6 |
| d6 hud 监听 gold_changed，但没有人发出 | 是 | 11 |
| d7 客户端调用 /api/match/report，服务端没有路由 | 是 | 7 |

| 共同根因 | 期望 | 排名 | 前 3 |
|---|---|---|---|
| cc1 | ent:state:shop:py/gold | 1 | ent:state:shop:py/gold, ent:table:main:ledger, ent:state:shop:py/matches_played |
| cc2 | ent:symbol:shop:server/wallet.py#add_gold | 7 | ent:state:shop:py/matches_played, ent:state:shop:py/gold, ent:table:main:ledger |
| cc3 | ent:state:shop:py/gold | 1 | ent:state:shop:py/gold, ent:table:main:ledger, ent:state:shop:py/matches_played |

## 推理：Agent 端到端（脚本策略）

合计 4 次运行：根因得分 0.500，错误事实 0，覆盖 0.625，推理缺陷 7 个，系统指出 0 个（0.000），误报 0；模型调用 29 次，约 29383 token。

| 场景 / 策略 | 结果 | 根因 | 覆盖 | 推理缺陷 | 系统指出 | 误报 | 调用 |
|---|---|---|---|---|---|---|---|
| buy-does-nothing / careful_basic | done | 0.500 | 1.000 | unsupported_conclusion | 无 | 无 | 8 |
| buy-does-nothing / competing_open | done | 0.500 | 0.500 | chain_gap, competing_open, false_lead_asserted, unsupported_conclusion | 无 | 无 | 5 |
| reconnect-double-reward / careful_cluster | done | 1.000 | 1.000 | 无 | 无 | 无 | 13 |
| reconnect-double-reward / jumps_to_conclusion | done | 0.000 | 0.000 | false_lead_asserted, unsupported_conclusion | 无 | 无 | 3 |

推理缺陷的定义：
- `unclaimed_conclusion`：交付了答案，但背后没有任何有效的因果主张
- `unsupported_conclusion`：交付了答案，但它依赖的因果主张没有一条经过验证
- `false_lead_asserted`：有效的因果主张指向已知的错误线索
- `competing_open`：两个以上互相竞争的因果假设仍未排除，且彼此不构成推理链
- `chain_gap`：某条有效的因果主张没有通过主张链连接到报告的症状

## 上下文（小预算长任务，脚本策略）

| 场景 | 策略 | 结果 | 超出预算的请求 | 峰值 / 预算 | 重写上下文 | 输入字符 | 证据 ID 完整保留 | 证据可找回 | 主张当前状态可见 |
|---|---|---|---|---|---|---|---|---|---|
| long-investigation（6000 token） | M5 之前 | done | 3/19 | 1.118 | 0 | 270511 | 1.000 | 1.000 | 1.000 |
| long-investigation（6000 token） | M5（当前） | done | 0/19 | 0.888 | 3 | 256154 | 0.833 | 1.000 | 1.000 |
