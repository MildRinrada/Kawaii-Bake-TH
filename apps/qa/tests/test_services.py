"""Service tests: visibility, ownership, the accepted-answer invariant,
and the notification wiring."""

from __future__ import annotations

from django.test import TestCase

from apps.notifications.constants import NotificationEventType
from apps.notifications.models import Notification, NotificationPreference
from apps.qa.constants import ThreadStatus
from apps.qa.exceptions import (
    AnswerNotFoundError,
    InvalidAcceptError,
    ModerationNotAllowedError,
    ThreadNotActiveError,
    ThreadNotFoundError,
    ThreadTargetNotFoundError,
)
from apps.qa.models import QuestionAnswer, QuestionThread
from apps.qa.selectors import qa_selector
from apps.qa.services import answer_service, thread_service
from apps.qa.tests.factories import create_answer, create_thread
from apps.recipes.constants import RecipeVisibility
from apps.recipes.tests.factories import create_published_recipe
from apps.users.tests.factories import create_user


class ThreadCreationTests(TestCase):
    """Target resolution through public refs."""

    def setUp(self) -> None:
        self.asker = create_user(username="qaasker")
        self.chef = create_user(username="qachef")

    def test_thread_on_visible_recipe(self) -> None:
        recipe = create_published_recipe(author=self.chef, slug="qa-cake")
        thread = thread_service.create_thread(
            author_id=self.asker.id,
            kind="recipe",
            slug=recipe.slug,
            data={"title": "อบกี่นาที?", "body": ""},
        )
        self.assertEqual(thread.recipe_id, recipe.id)
        self.assertIsNone(thread.course_id)

    def test_hidden_recipe_target_is_404(self) -> None:
        secret = create_published_recipe(
            author=self.chef, slug="qa-secret", visibility=RecipeVisibility.PRIVATE
        )
        with self.assertRaises(ThreadTargetNotFoundError):
            thread_service.create_thread(
                author_id=self.asker.id,
                kind="recipe",
                slug=secret.slug,
                data={"title": "?"},
            )

    def test_thread_survives_target_deletion(self) -> None:
        recipe = create_published_recipe(author=self.chef, slug="qa-doomed")
        thread = thread_service.create_thread(
            author_id=self.asker.id,
            kind="recipe",
            slug=recipe.slug,
            data={"title": "?"},
        )
        create_answer(thread=thread, author=self.chef)
        recipe.delete()

        thread.refresh_from_db()
        self.assertIsNone(thread.recipe_id)
        self.assertEqual(thread.answers.count(), 1)


class VisibilityTests(TestCase):
    """One prefix-parameterised rule for threads and their answers."""

    def setUp(self) -> None:
        self.asker = create_user(username="qavis")
        self.stranger = create_user(username="qavisstr")
        self.staff = create_user(username="qavisstaff", is_staff=True)

    def test_hidden_thread_visible_to_author_and_staff_only(self) -> None:
        hidden = create_thread(author=self.asker, status=ThreadStatus.HIDDEN)

        self.assertIsNone(qa_selector.get_thread(thread_id=hidden.pk))
        self.assertIsNone(
            qa_selector.get_thread(thread_id=hidden.pk, viewer_id=self.stranger.id)
        )
        self.assertIsNotNone(
            qa_selector.get_thread(thread_id=hidden.pk, viewer_id=self.asker.id)
        )
        self.assertIsNotNone(
            qa_selector.get_thread(
                thread_id=hidden.pk,
                viewer_id=self.staff.id,
                viewer_is_staff=True,
            )
        )

    def test_deleted_thread_visible_to_no_one(self) -> None:
        deleted = create_thread(author=self.asker, status=ThreadStatus.DELETED)
        for viewer_id, staff in ((None, False), (self.asker.id, False), (self.staff.id, True)):
            self.assertIsNone(
                qa_selector.get_thread(
                    thread_id=deleted.pk, viewer_id=viewer_id, viewer_is_staff=staff
                )
            )

    def test_answers_inherit_the_thread_rule(self) -> None:
        hidden = create_thread(author=self.asker, status=ThreadStatus.HIDDEN)
        answer = create_answer(thread=hidden, author=self.stranger)

        self.assertEqual(
            qa_selector.list_answers(thread_id=hidden.pk).count(), 0
        )
        self.assertIsNone(qa_selector.get_answer(answer_id=answer.pk))
        # The author of the hidden thread still sees its answers.
        self.assertEqual(
            qa_selector.list_answers(
                thread_id=hidden.pk, viewer_id=self.asker.id
            ).count(),
            1,
        )


class ManagementTests(TestCase):
    """Edit, moderate, soft-delete."""

    def setUp(self) -> None:
        self.asker = create_user(username="qamgr")
        self.stranger = create_user(username="qamgrstr")
        self.staff = create_user(username="qamgrstaff", is_staff=True)
        self.thread = create_thread(author=self.asker)

    def test_author_edits_title_and_body(self) -> None:
        thread = thread_service.update_thread(
            thread_id=self.thread.pk,
            viewer_id=self.asker.id,
            data={"title": "แก้หัวข้อ", "body": "แก้เนื้อหา"},
        )
        self.assertEqual(thread.title, "แก้หัวข้อ")

    def test_stranger_cannot_edit_or_delete(self) -> None:
        with self.assertRaises(ThreadNotFoundError):
            thread_service.update_thread(
                thread_id=self.thread.pk,
                viewer_id=self.stranger.id,
                data={"title": "แอบ"},
            )
        with self.assertRaises(ThreadNotFoundError):
            thread_service.delete_thread(
                thread_id=self.thread.pk, viewer_id=self.stranger.id
            )

    def test_non_staff_cannot_moderate(self) -> None:
        with self.assertRaises(ModerationNotAllowedError):
            thread_service.update_thread(
                thread_id=self.thread.pk,
                viewer_id=self.asker.id,
                data={"status": ThreadStatus.HIDDEN},
            )

    def test_staff_hides_and_restores(self) -> None:
        thread_service.update_thread(
            thread_id=self.thread.pk,
            viewer_id=self.staff.id,
            viewer_is_staff=True,
            data={"status": ThreadStatus.HIDDEN},
        )
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, ThreadStatus.HIDDEN)

    def test_soft_delete_keeps_history_but_hides_everything(self) -> None:
        create_answer(thread=self.thread, author=self.stranger)
        thread_service.delete_thread(
            thread_id=self.thread.pk, viewer_id=self.asker.id
        )

        self.assertTrue(QuestionThread.objects.filter(pk=self.thread.pk).exists())
        self.assertEqual(QuestionAnswer.objects.count(), 1)
        self.assertIsNone(
            qa_selector.get_thread(thread_id=self.thread.pk, viewer_id=self.asker.id)
        )


class AnswerTests(TestCase):
    """Answer lifecycle and its notification."""

    def setUp(self) -> None:
        self.asker = create_user(username="qaans")
        self.helper = create_user(username="qahelper")
        self.thread = create_thread(author=self.asker)

    def test_answer_notifies_the_asker(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            answer_service.create_answer(
                author_id=self.helper.id,
                thread_id=self.thread.pk,
                data={"body": "ลองลดไฟลงค่ะ"},
            )
        row = Notification.objects.get(recipient=self.asker)
        self.assertEqual(row.event_type, NotificationEventType.QA_ANSWER_RECEIVED)
        self.assertEqual(row.actor_handle, "qahelper")
        self.assertIn(self.thread.title, row.body)

    def test_self_answer_does_not_notify(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            answer_service.create_answer(
                author_id=self.asker.id,
                thread_id=self.thread.pk,
                data={"body": "หาคำตอบเองได้แล้ว"},
            )
        self.assertEqual(Notification.objects.count(), 0)

    def test_hidden_thread_cannot_be_answered(self) -> None:
        hidden = create_thread(author=self.asker, status=ThreadStatus.HIDDEN)
        # Stranger: cannot even see it  404.
        with self.assertRaises(ThreadNotFoundError):
            answer_service.create_answer(
                author_id=self.helper.id, thread_id=hidden.pk, data={"body": "x"}
            )
        # Author: sees it, but it is not open  409.
        with self.assertRaises(ThreadNotActiveError):
            answer_service.create_answer(
                author_id=self.asker.id, thread_id=hidden.pk, data={"body": "x"}
            )

    def test_author_edits_and_deletes_own_answer_only(self) -> None:
        answer = create_answer(thread=self.thread, author=self.helper)

        with self.assertRaises(AnswerNotFoundError):
            answer_service.update_answer(
                answer_id=answer.pk, viewer_id=self.asker.id, data={"body": "แอบ"}
            )

        updated = answer_service.update_answer(
            answer_id=answer.pk, viewer_id=self.helper.id, data={"body": "แก้แล้ว"}
        )
        self.assertEqual(updated.body, "แก้แล้ว")

        answer_service.delete_answer(answer_id=answer.pk, viewer_id=self.helper.id)
        self.assertFalse(QuestionAnswer.objects.filter(pk=answer.pk).exists())


class AcceptedAnswerTests(TestCase):
    """The at-most-one invariant, replacement, and clearing."""

    def setUp(self) -> None:
        self.asker = create_user(username="qaacc")
        self.helper = create_user(username="qaacchelper")
        self.other = create_user(username="qaaccother")
        self.thread = create_thread(author=self.asker)
        self.first = create_answer(thread=self.thread, author=self.helper)
        self.second = create_answer(thread=self.thread, author=self.other)

    def test_only_the_asker_accepts(self) -> None:
        with self.assertRaises(ThreadNotFoundError):
            thread_service.accept_answer(
                thread_id=self.thread.pk,
                answer_id=self.first.pk,
                viewer_id=self.helper.id,
            )

    def test_accept_notifies_the_answerer(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            thread = thread_service.accept_answer(
                thread_id=self.thread.pk,
                answer_id=self.first.pk,
                viewer_id=self.asker.id,
            )
        self.assertEqual(thread.accepted_answer_id, self.first.pk)
        row = Notification.objects.get(recipient=self.helper)
        self.assertEqual(row.event_type, NotificationEventType.QA_ANSWER_ACCEPTED)

    def test_replacing_unsets_the_old_in_the_same_write(self) -> None:
        thread_service.accept_answer(
            thread_id=self.thread.pk, answer_id=self.first.pk, viewer_id=self.asker.id
        )
        thread = thread_service.accept_answer(
            thread_id=self.thread.pk,
            answer_id=self.second.pk,
            viewer_id=self.asker.id,
        )
        self.assertEqual(thread.accepted_answer_id, self.second.pk)

    def test_re_accepting_the_same_answer_does_not_re_notify(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            thread_service.accept_answer(
                thread_id=self.thread.pk,
                answer_id=self.first.pk,
                viewer_id=self.asker.id,
            )
            thread_service.accept_answer(
                thread_id=self.thread.pk,
                answer_id=self.first.pk,
                viewer_id=self.asker.id,
            )
        self.assertEqual(Notification.objects.filter(recipient=self.helper).count(), 1)

    def test_foreign_answer_is_rejected(self) -> None:
        other_thread = create_thread(author=self.other, title="อีกกระทู้")
        foreign = create_answer(thread=other_thread, author=self.helper)
        with self.assertRaises(InvalidAcceptError):
            thread_service.accept_answer(
                thread_id=self.thread.pk,
                answer_id=foreign.pk,
                viewer_id=self.asker.id,
            )

    def test_deleting_the_accepted_answer_clears_the_pointer(self) -> None:
        thread_service.accept_answer(
            thread_id=self.thread.pk, answer_id=self.first.pk, viewer_id=self.asker.id
        )
        answer_service.delete_answer(
            answer_id=self.first.pk, viewer_id=self.helper.id
        )
        self.thread.refresh_from_db()
        self.assertIsNone(self.thread.accepted_answer_id)

    def test_opt_out_preference_silences_accept(self) -> None:
        NotificationPreference.objects.create(
            user=self.helper,
            event_type=NotificationEventType.QA_ANSWER_ACCEPTED,
            enabled=False,
        )
        with self.captureOnCommitCallbacks(execute=True):
            thread_service.accept_answer(
                thread_id=self.thread.pk,
                answer_id=self.first.pk,
                viewer_id=self.asker.id,
            )
        self.assertEqual(Notification.objects.count(), 0)
