# ADR 0032 - Community interactions: likes and comments

- **Status:** accepted
- **Date:** 2026-08-11
- **Phase:** community completion

## Context

`GalleryPost` shipped with a docstring that read *"No like/comment/view
counters - interactions are a future phase, and when they arrive they
will aggregate live."* The feed reached the point that gap defined: a
community page with no way to react is a wall of photos nobody has a
reason to revisit, and the page had to *tell* people so in a sidebar
note. This ADR closes it.

## Decisions

### 1. A row is the interaction; counts are aggregated, never stored

`GalleryLike(post, user, created_at)` with a unique `(post, user)`
constraint, and `GalleryComment(post, author, body)`. There is no
`like_count` column: the selector annotates `Count("likes")` /
`Count("comments")` and an `Exists` subquery for `viewer_has_liked`, so
the feed stays one query and no counter can drift from its rows. The
model docstring's promise is kept exactly as written.

### 2. Liking is idempotent at the database, not in application code

`like_post` inserts and catches `IntegrityError` inside a savepoint
(the enrollment precedent). Two taps in flight end as one like without a
read-then-write race. Unliking is a filtered delete - also idempotent,
so a double-tap on a slow connection cannot 404.

### 3. Interactions inherit the post's visibility, and its 404

Every write resolves the post through `gallery_selector.get_post` first,
so an unpublished post cannot be liked, commented on, or have its
comments listed - all with the same 404 an absent post gives. A stranger
must not be able to confirm a hidden post exists by the shape of a
refusal.

### 4. Comments are leaves; deletion is hard and three-party

Nothing references a comment, so `CASCADE` from either the post or the
account is correct and deletion is hard (the Q&A answer precedent).
A comment is removable by **its author, the owner of the post it sits
on, or staff** - your wall, your call - and anyone else gets a 404
rather than a 403, so comment ids stay unenumerable.

### 5. One new notification type, opt-out like every other

`gallery_comment` joins `NotificationEventType` (an ADR/docs change per
ADR 0016, not just another `notify` call), links to
`/community/posts/{id}/`, honours the same per-event preference, and is
never sent to yourself. Likes deliberately produce **no** notification:
a like is cheap to give and would make the inbox unusable at any real
volume; the count on the post is the feedback.

## Consequences

- `GET /gallery/` gains `like_count`, `comment_count` and
  `viewer_has_liked` on every post; anonymous viewers get real counts
  and `false`, never a personalised flag invented for them.
- The community card's action row now carries real interactions, and the
  owner's edit/hide/delete moves into a `⋯` menu - a destructive action
  no longer sits beside "share" looking the same.
- The "likes and comments are not available yet" copy is gone from the
  sidebar; what replaced it describes what the buttons actually do.
- Bookmarks/saving a post remain unbuilt and are still stated as such.
