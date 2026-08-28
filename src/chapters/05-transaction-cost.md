---
chapter: 5
title: "交易成本与路径依赖"
subtitle: "Transaction Costs and Path Dependence"
lecture_num: 5
slug: "05-transaction-cost"
date: "2026-08-02"
author: "「开源之道」·适兕"
---

## 引子

罗纳德·科斯开创性的作品《企业的性质》[^coase1937] 引出了交易成本，给出企业存在的缘由，更重要的是将交易成本引入了经济学分析。法学教授 Yochai Benkler，则回答了开源项目共同体就是实现这个的重要途径，前提就是实现相应的目标。

本期讲座以交易成本和制度经济学等经济理论，来解释开源现象，尤其是各类非交易性的软件开发。

## 毋需法律的秩序

在没有雇佣关系、没有层级命令、没有价格信号的世界中，如何协调大规模协作？这是一个经济学长期回避的问题。传统经济学假设交易必须通过法律契约来保障——但在开源世界，协作的发生并不依赖于正式的法律合同。

这并不意味着法律不重要，而是意味着开源找到了一种"毋需法律的秩序"——一种基于社区规范、声誉机制和社会资本的自发协作秩序。

## 交易成本与法律经济学

科斯的洞察是：市场交易并非免费的。每一次谈判、签约、执行都需要成本。当这些成本超过组织内部协调的成本时，企业就出现了。

开源将交易成本进一步降低——甚至趋近于零。任何人可以无条件试用代码，可以自定义修改，可以将更多成本降至最低。与购买软件需要经历的协商、合同、交付流程相比，开源极大地降低了交易成本。

## 科斯的贡献

科斯在《企业的性质》[^coase1937] 和《社会成本问题》中提出的核心问题是：为什么市场不能总是最优？答案是：交易成本的存在使得企业（层级组织）在特定条件下比市场更高效。

Benkler 在《网络的富饶》[^benkler2006] 中提出了第三种选项：既非市场也非层级，而是"对等生产"（peer production）——开源项目共同体就是这种模式的具体体现。

## 信息的特殊性

信息作为一种经济物品，具有独特的属性：

- **非竞争性**（Non-rivalry）：一个人使用信息不阻止他人同时使用
- **非排他性**（Non-excludability）：一旦信息被公开，很难阻止他人获取
- **高固定成本，低边际成本**：初始创作成本高，复制成本趋近于零

这些属性决定了信息商品天然抗拒传统市场定价机制。开源是信息经济学的一个具体答案。

## 何谓路径依赖

路径依赖（Path Dependence）是指：过去的制度选择约束了未来的可能性空间。Paul A. David[^david2000] 的 QWERTY 键盘案例是经典：一个非最优的设计因早期的先发优势而被锁定。

开源软件具有强烈的路径依赖特征：一旦一个社区采用了某个开源平台，迁移成本（learning cost、compatibility cost、ecosystem cost）使得切换极其困难。这就是 Linux、Kubernetes、Python 等开源项目持续发展的核心本质之一。

## 开源是如何吞噬软件的

从操作系统（Linux）到数据库（MySQL、PostgreSQL），从编程语言（Python、Rust）到云计算基础设施（Kubernetes）——开源正在系统性地取代专有软件。这一过程不是市场的自然演化，而是制度选择的结果：开源在降低交易成本方面具有结构性优势。

---

## 延伸阅读

- Coase, "The Nature of the Firm," *Economica*, 1937[^coase1937]
- Coase, "The Problem of Social Cost," *Journal of Law and Economics*, 1960
- Benkler, *The Wealth of Networks*, Yale Press, 2006[^benkler2006]
- David, P. A., "Path Dependence," January 2000[^david2000]
- 《技术的本质》，Brian Arthur，浙江人民出版社，2014
- 《组织的逻辑》，Ray Fisman / Tim Sullivan，九州出版社，2023
- Nagle, Seamans, Tadelis, "Transaction Cost Economics in the Digital Economy," HBS Working Paper 21-009
- Foray, D., *The Economics of Knowledge*, MIT Press, 2006

[^coase1937]: Ronald H. Coase, "The Nature of the Firm," *Economica* 4(16), 386-405, 1937.
[^benkler2006]: Yochai Benkler, *The Wealth of Networks: How Social Production Transforms Markets and Freedom*, Yale University Press, 2006.
[^david2000]: Paul A. David, "Path Dependence, Its Critics and the Quest for Historical Economics," January 2000.
