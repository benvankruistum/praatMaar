# Final fix report

## Overlapping STT question revisions

- Added source-window tracking to question heuristics.
- Question-shaped finals that substantially overlap an open question's source window, or are highly text-similar, are treated as revisions.
- Revisions neither add a duplicate question nor mark the original as `possibly_answered`.
- Added a regression test covering overlapping finals with slightly revised wording.
- Focused verification: `python -m pytest tests/test_meeting_buddy_heuristics.py -q`.
