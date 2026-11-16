# PRD: a committed backstop liquidator for the Coinbase cbBTC market

Draft for a One Lever post (Sat Nov 28). Not approved. Line numbers cite `WRITEUP.md` at `origin/main` 4f22d02.

## User
Suppliers to the Morpho cbBTC/USDC market on Base that funds Coinbase's BTC-backed loans. They lend USDC; a crash that outruns liquidators lands on them. The decision-maker is Coinbase, the only party that can redeem cbBTC and sell BTC on its own book.

## Problem
The market lends at 86% LLTV. On a March 2020 replay the loss by end of path is $9.2M (0.6% of supply), but at the trough $158.4M (10.0%) sits underwater with no liquidator able to act (L15, L90). The two measures are taken at different moments and never added. Cutting the LLTV to 77% still leaves 8.4% unserved, because liquidator capital, not the haircut, binds (L15, L116). The only capital measurement is the busiest day, Feb 5 2026, which did not bind, so it is a floor, not an estimate (L41, L279).

## Mechanism
A written commitment by Coinbase to act as liquidator of last resort: redeem cbBTC 1:1 and sell BTC on its own book when a position crosses LLTV. In the model this is the ABC scenario. Nothing public says it exists today (L84, L284). Result in the replay: $0 unserved and $13.1M (0.8%) realized loss at 86% (L15, L100). The LLTV cut to 80% / 66-70% draw comes second (L15).

## One metric
Supply left unserved at the trough on the March 2020 path, as a share of cbBTC supply. Today's modeled value: 10.0%. Target with the commitment: 0%.

## Live figure (dated)
Spine's own alert (issue #11, snapshot 2026-10-24T19:35:54Z): at a -6% cbBTC price move, liquidatable borrow was $19.5M against modeled liquidator capacity of $12.9M. The issue has stayed open since. This is the latest figure recorded in the repo; no fresher fetch was run for this draft. TODO: re-run the alert on posting day and replace this line with that snapshot, or post without it.

## Guardrail
Realized loss on the other six paths stays at or below today's (WRITEUP L15: at 80% every other path is clean). The commitment must not move losses to the backstop's balance sheet on a path where the price does not bounce: the 1-day-hold case takes the 86% loss from $9.2M to $38.1M (2.4% of supply) (L279). State that cost.

## What disproves it
- Evidence Coinbase already liquidates its own book. Then the ABC column describes the status quo and the 10.0% is overstated (L284).
- A measured crash where liquidators supplied more than the Feb 5 floor ($96.8M repaid in the day, L41) and cleared the book. The metric would be shown to bind less than modeled (L279).
- Depth in a crash scaled from today turns out wrong (WRITEUP section 7): the replay's unserved share then moves with it.

## Non-goals
No claim that a loss will happen. No Coinbase contact or message. Not a recommendation to lend or not lend.
