from core.serializers.notification_serializer import NotificationSerializer
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Notification


class NotificationListView(generics.ListAPIView):
    """
    GET /notifications/

    Returns the authenticated user's notifications, newest first.

    Optional query params:
      ?is_read=true|false
      ?type=REPORT_SUBMITTED|REPORT_REVIEWED|INTERNSHIP_STATUS_CHANGED|GENERAL
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)

        is_read = self.request.query_params.get("is_read")
        notif_type = self.request.query_params.get("type")

        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == "true")
        if notif_type:
            qs = qs.filter(notification_type=notif_type.upper())

        return qs  # already ordered by Meta


class MarkNotificationReadView(APIView):
    """PATCH /notifications/{pk}/read/  — mark a single notification as read."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(
            {"message": "Notification marked as read.", "id": notification.id},
            status=status.HTTP_200_OK,
        )


class MarkAllNotificationsReadView(APIView):
    """PATCH /notifications/read-all/  — mark every unread notification as read."""

    permission_classes = [IsAuthenticated]

    def patch(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response(
            {"message": "All notifications marked as read.", "updated": updated},
            status=status.HTTP_200_OK,
        )
