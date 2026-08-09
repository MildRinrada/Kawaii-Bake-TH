/**
 * Convenience aliases over the generated OpenAPI types.
 *
 * `types.ts` is generated from the backend schema (`npm run
 * generate:api-types`) and never edited by hand; this module gives the
 * app short names for the shapes it actually touches. Add aliases as
 * screens need them — never redefine a shape by hand.
 */

import type { components } from "@/lib/api/types";

export type Schemas = components["schemas"];

export type OwnProfile = Schemas["OwnProfile"];
export type PublicProfile = Schemas["PublicProfile"];
export type UserPreference = Schemas["UserPreference"];
export type MySettings = Schemas["MySettings"];

export type RecipeListItem = Schemas["RecipeListItem"];
export type RecipeDetail = Schemas["RecipeDetail"];
export type CourseListItem = Schemas["CourseListItem"];
export type CourseDetail = Schemas["CourseDetail"];
export type LessonSyllabusItem = Schemas["LessonSyllabusItem"];
export type LessonDetail = Schemas["LessonDetail"];
export type MyCourseProgress = Schemas["MyCourseProgress"];

export type Review = Schemas["Review"];
export type FavoriteItem = Schemas["FavoriteItem"];
export type NotificationItem = Schemas["Notification"];
export type NotificationList = Schemas["NotificationList"];

export type Conversation = Schemas["Conversation"];
export type ConversationDetail = Schemas["ConversationDetail"];
export type Message = Schemas["Message"];

export type Category = Schemas["Category"];
export type GalleryPost = Schemas["GalleryPost"];
export type QaThread = Schemas["Thread"];

export type Certificate = Schemas["Certificate"];
export type Achievement = Schemas["Achievement"];
export type RecommendedRecipe = Schemas["RecommendedRecipe"];
export type RecommendedCourse = Schemas["RecommendedCourse"];

/** Authentication state — carries the caller's own `is_staff` (ADR 0022). */
export type Me = Schemas["Me"];
/** A badge definition from the catalogue — what there is to earn (ADR 0024). */
export type Badge = Schemas["Badge"];
export type GamificationSummary = Schemas["GamificationSummary"];
export type QuizListItem = Schemas["QuizListItem"];
export type OwnerQuestion = Schemas["OwnerQuestion"];
export type QaAnswer = Schemas["Answer"];
export type RewardSummary = Schemas["RewardSummary"];
export type RewardTransaction = Schemas["RewardTransaction"];
