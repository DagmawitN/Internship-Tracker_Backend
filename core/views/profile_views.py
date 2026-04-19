from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import cloudinary.uploader

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        return Response(self._build_response(request.user))

    def patch(self, request):
        user = request.user

        # USER UPDATE 
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name = request.data.get("last_name", user.last_name)
        user.phone = request.data.get("phone", user.phone)
        user.save()

        # PROFILE UPDATE
        profile = user.profile
        profile.bio = request.data.get("bio", profile.bio)
        profile.location = request.data.get("location", profile.location)

        # AVATAR UPDATE 
        if "avatar" in request.FILES:
            # delete old avatar to save space
            if profile.avatar and profile.avatar.public_id:
                cloudinary.uploader.destroy(profile.avatar.public_id)

            profile.avatar = request.FILES["avatar"]

        profile.save()

        # STUDENT UPDATE
        if hasattr(user, "student_profile"):
            student = user.student_profile
            department = request.data.get("department")

            if department:
                student.department_id = department  
                student.save()

        return Response(
            {
                "message": "Profile updated successfully",
                "data": self._build_response(user)
            },
            status=status.HTTP_200_OK
        )

    def _build_response(self, user):
        """Reusable response builder"""

       
        avatar_url = None
        if user.profile.avatar:
            avatar_url = user.profile.avatar.build_url(
                width=300,
                height=300,
                crop="fill",
                gravity="face"
            )

        data = {
            "id": user.id,
            "email": user.email,
            "role": user.role.role_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "profile": {
                "bio": user.profile.bio,
                "avatar": avatar_url,
                "location": user.profile.location
            }
        }

        if hasattr(user, "student_profile"):
            data["student"] = {
                "student_id": user.student_profile.student_id,
                "department": user.student_profile.department.department_name
            }

        if hasattr(user, "staff_profile"):
            data["staff"] = {
                "department": user.staff_profile.department.department_name
            }

        return data