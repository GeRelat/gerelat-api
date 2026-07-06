import os

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    ChangePasswordSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
    build_password_reset_payload,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Senha alterada com sucesso."})


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        if user is not None:
            payload = build_password_reset_payload(user)
            frontend_base_url = os.getenv(
                "FRONTEND_BASE_URL", "http://localhost:8080"
            ).rstrip("/")
            reset_url = (
                f"{frontend_base_url}/"
                f"?page=resetar-senha"
                f"&uid={payload['uid']}&token={payload['token']}"
            )
            send_mail(
                "Redefinição de senha - GeRelat",
                (
                    "Uma solicitação de redefinição de senha foi recebida.\n\n"
                    f"Acesse o link a seguir para cadastrar uma nova senha:\n{reset_url}\n"
                ),
                os.getenv("DEFAULT_FROM_EMAIL", "noreply@gerelat.local"),
                [user.email],
                fail_silently=True,
            )

        return Response(
            {
                "detail": (
                    "Se o e-mail estiver cadastrado, as instruções de "
                    "redefinição foram enviadas."
                )
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Senha redefinida com sucesso."},
            status=status.HTTP_200_OK,
        )
