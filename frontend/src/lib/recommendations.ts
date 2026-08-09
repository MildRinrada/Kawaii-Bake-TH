/**
 * Thai labels for the backend's deterministic recommendation reason
 * codes (apps/recommendation/constants.py — fixed vocabulary).
 */
export const REASON_LABELS: Record<string, string> = {
  matches_your_favorite_categories: "ตรงหมวดที่คุณชอบ",
  similar_to_your_favorites: "คล้ายของที่คุณถูกใจ",
  similar_to_content_you_reviewed: "คล้ายของที่คุณรีวิว",
  based_on_your_courses: "จากคอร์สที่คุณเรียน",
  from_a_creator_you_like: "จากคนที่คุณติดตามผลงาน",
  highly_rated: "คะแนนรีวิวสูง",
  popular: "กำลังเป็นที่นิยม",
  recently_published: "มาใหม่",
};
