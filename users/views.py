from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    username = serializers.RegexField(r"^[A-Za-z0-9@.+_-]{3,30}$", max_length=30)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=4)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")
        read_only_fields = ("id",)

    def validate(self, attrs):
        
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except AuthenticationFailed:
            raise serializers.ValidationError({"non_field_errors": ["Identifiants invalides."]})


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        player = serializer.save()
        return Response(PublicUserSerializer(player).data, status=status.HTTP_201_CREATED)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PublicUserSerializer(request.user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_value = request.data.get("refresh")
        if not refresh_value:
            return Response({"refresh": ["Ce champ est requis."]}, status=400)
        try:
            RefreshToken(refresh_value).blacklist()
        except TokenError:
            return Response({"refresh": ["Jeton invalide ou déjà révoqué."]}, status=400)
        return Response(status=status.HTTP_205_RESET_CONTENT)
