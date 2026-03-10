---
title: "Search vs. Recommendation: In-Batch Contrastive Loss Design Differences"
date: 2026-03-01
tags:
  - recommender systems
  - contrastive learning
  - contrastive loss
  - two-tower model
  - session mask
lang: en
chinese: recommender-systems/training/in-batch-contrastive-loss
---

> 🌐 [中文版](./in-batch-contrastive-loss.md)

In-Batch Softmax Contrastive Loss is standard practice in search — encode query and doc with a two-tower model, compute cross scores within the batch, and use softmax cross-entropy to pull positive pairs together and push negatives apart. But when you migrate this approach to recommendation, you'll find the two domains have fundamentally different data structures. Copying it directly will cause problems. This post breaks down those differences and how they shape positive/negative sample selection and session mask design.

---

## 1. Background: What In-Batch Contrastive Loss Does

Quick recap: given B (user, item) pairs in a batch, encode each and compute a B×B similarity matrix. The diagonal is the true pairing; all other positions naturally serve as negatives. Apply softmax cross-entropy per row to make correct pairs score higher than incorrect ones.

The core advantage: **no need to construct negatives explicitly** — other items in the batch are naturally negatives. Larger batch = more negatives = richer signal.

The ultimate goal isn't the contrastive loss itself, but **producing high-quality semantic embeddings** to inject into downstream ranking models and improve CTR.

---

## 2. The Fundamental Data Structure Difference

**Search: one query maps to multiple docs.**

A single search request returns multiple results; users click some and skip others, producing multiple training samples with identical queries but different docs:

```
query="King of Glory" → doc_0="Zhang Daxian tutorial"   label=1
query="King of Glory" → doc_1="King of Glory strategy"  label=0
query="King of Glory" → doc_2="King of Glory skins"     label=0
```

**Recommendation: each sample typically comes from a different user.**

Recommendation training data consists of (user, item) pairs from different users mixed in the same batch:

```
User A → item_0 (gaming)   label=1
User B → item_1 (makeup)   label=0
User C → item_2 (battle royale) label=1
```

This difference looks simple but directly impacts two key design decisions: positive/negative sample selection and session masking.

---

## 3. Sample Selection: Search Uses Positives Only; Recommendation Uses Both

### Why Search Uses Only Positive Samples

In the search example, all three samples share the same query, so the user encoder produces nearly identical user_output for each. If all three participate in contrastive loss, the similarity matrix will have nearly duplicate rows:

```
              doc_0    doc_1    doc_2    ...other docs
user_0(KoG)   0.9      0.85     0.8     0.1
user_1(KoG)   0.9      0.85     0.8     0.1   ← almost identical
user_2(KoG)   0.9      0.85     0.8     0.1   ← almost identical
```

Duplicate rows cause conflicting gradients — user_0's row wants to push doc_0 up and doc_1 down, but user_1's row (label=0) doesn't push doc_1 up, yet both rows have nearly identical user_output but different targets.

The fix: **keep only positive samples**, one per query. No duplicate rows, clean signal. Negatives all come from other queries' positive docs.

### Why Recommendation Can Use Both Positive and Negative Samples

In recommendation, each sample comes from a different user, so user_output is unique per row — no duplicate row problem. Negative items make excellent contrastive targets: different-category items provide strong discriminative signal. Including both positives and negatives gives richer training signal.

---

## 4. Session Mask: Same Problem, Different Solutions

Both domains face the same core problem: **multiple positive samples from the same user in the same request cannot serve as negatives for each other.**

If User A searched for "King of Glory" and clicked both Zhang Daxian and Meng Lei, both docs are correct results. Using them as negatives for each other sends contradictory gradients — push Zhang Daxian up while pushing Meng Lei down, but both are correct.

The two domains solve this differently:

**Search: all-or-nothing — keep only positives.** Keep one positive sample per query, discard everything else (including negatives from that query). Simple but effective; negatives come from other queries' docs, so there's no shortage of contrastive signal.

**Recommendation: fine-grained — Session Mask.** Recommendation can't simply discard negatives (they need to participate in contrastive learning), so session mask is used to block only other positive samples from the same request, while keeping everything else.

Example: User A's single request produces 4 samples:

```
req_1, User A → item_0 (gaming)    label=1
req_1, User A → item_1 (battle royale) label=1
req_1, User A → item_2 (beauty)    label=0
req_1, User A → item_3 (dance)     label=0
```

For sample 0 (User A → item_0), session mask handles:

- item_1: same request + positive → **mask** (User A also clicked this, can't be a negative)
- item_2: same request + negative → **keep** (User A didn't click, fine as a negative)
- item_3: same request + negative → **keep** (User A didn't click, fine as a negative)
- Items from other requests → **keep** (different users, no contradiction)

Masked positions get scores set to -1e9, so their softmax probability approaches 0 — they participate neither as positives nor negatives.

### When to Mask, When Not to Mask

The rule is simple — **only mask when: same user, same request, both are positives**:

- Same user, same request, both positives → **mask**. Identical user_output; using one as a negative for the other creates contradictory gradients.
- Same user, same request, one positive + one negative → **don't mask**. The negative is something the user didn't click — it's a valid negative.
- Same user, different requests → **don't mask**. User state may have changed between requests (history sequence updated); these are independent recommendation decisions.
- Different users → **don't mask**. Regardless of whether they like the same category, different user_outputs means no contradiction. Contrastive loss learns relative ranking, not absolute preference.

### When There's No request_id

If training data temporarily lacks a request_id, the correct approach is **no masking at all** (session_mask = all False). A common mistake is mocking all samples with the same session_id, which makes the system think all samples come from one request, causing all positive samples to mask each other and completely eliminating contrastive signal.

---

## 5. Positive/Negative Source Comparison

| | Search (after keeping positives only) | Recommendation (with Session Mask) |
|--|--------------------------------------|-------------------------------------|
| **Positives** | Current query's positive doc (diagonal, 1 per row) | Current user's positive item in current request (diagonal, 1 per row) |
| **Negatives** | Positive docs from other queries | Same-request negatives + other users' positives + other users' negatives |
| **Not in loss** | Other samples with same query (discarded) | Other positives in same request (session masked) |

Recommendation has richer negative sources. After search filtering, only "other queries' positive docs" remain; recommendation keeps within-request user-skipped items plus all items from other users.

---

## 6. Semantic Signal Strength Difference

Another key difference: the strength of semantic association between user and item.

**Search is direct matching.** query="King of Glory livestream", doc="Zhang Daxian King of Glory teaching livestream" — both texts describe the same thing. Semantic encoders learn this match easily.

**Recommendation is indirect inference.** The user side is a sequence of historical behaviors (texts of past items viewed), the item side is the candidate item's text. The model must infer "gaming user" from a history like ["PUBG finals", "League of Legends ranked tutorial", "Genshin Impact guide"] and then match it with "King of Glory rank-up tips". The signal is significantly weaker than search.

This means contrastive loss in recommendation is better suited as an **auxiliary loss**, jointly trained with the main CTR loss to add semantic alignment regularization to embeddings — not expected to deliver the large gains it achieves in search.

If semantic signal is too weak, consider: shortening the history sequence (only recent items, more focused interests), filtering user-side history by category, or using hard negative mining to increase discriminative power.

---

## 7. Summary

| | Search | Recommendation |
|--|--------|----------------|
| Data structure | One query maps to multiple docs | Different users mixed in one batch |
| Sample selection | Positives only (avoid duplicate query noise) | Both positives and negatives (no duplicate user issue) |
| Multi-positive handling | Discard all but one | Session Mask for fine-grained filtering |
| Negative sources | Other queries' positive docs | Same-request negatives + all other users' items |
| Semantic signal strength | Strong (direct query-doc matching) | Weaker (indirect user interest → candidate inference) |
| Contrastive loss role | Core training objective | Auxiliary loss alongside main CTR loss |

---

## Extended Reading

Recommendation systems can benefit from many ML efficiency optimization techniques from Transformer research. For example, Transformer's attention mechanism improvements can be applied to long user history sequence processing:

- [[flash-attention-varlen|Flash-Attention: Efficient Attention for Variable-Length Sequences]]（as a reference for long history sequence processing）
