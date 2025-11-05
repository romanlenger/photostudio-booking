from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from .. import models, schemas
from ..database import get_db
from ..security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_email_verification_token,
    create_password_reset_token,
    verify_token,
    get_current_user,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from ..email_service import send_verification_email, send_password_reset_email

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Реєстрація нового користувача"""
    
    # Перевірити чи email вже використовується
    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Користувач з таким email вже існує"
        )
    
    # Перевірити чи username вже використовується
    if db.query(models.User).filter(models.User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Користувач з таким username вже існує"
        )
    
    # Створити нового користувача
    new_user = models.User(
        email=user_data.email,
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=models.UserRole.CLIENT  # За замовчуванням всі клієнти
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Відправити email для верифікації
    verification_token = create_email_verification_token(new_user.email)
    background_tasks.add_task(
        send_verification_email,
        new_user.email,
        verification_token,
        new_user.username
    )
    
    return new_user

@router.post("/login", response_model=schemas.TokenResponse)
async def login(
    user_credentials: schemas.UserLogin,
    db: Session = Depends(get_db)
):
    """Вхід користувача"""
    
    user = db.query(models.User).filter(models.User.email == user_credentials.email).first()
    
    if not user or not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний email або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Акаунт деактивовано"
        )
    
    # Створити токени
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=schemas.TokenResponse)
async def refresh_token(
    token_data: schemas.TokenRefresh,
    db: Session = Depends(get_db)
):
    """Оновити access token використовуючи refresh token"""
    
    email = verify_token(token_data.refresh_token, "refresh")
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний refresh token"
        )
    
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Користувач не знайдений або деактивований"
        )
    
    # Створити нові токени
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.get("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    """Підтвердити email користувача"""
    
    email = verify_token(token, "email_verification")
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невірний або прострочений токен"
        )
    
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Користувач не знайдений"
        )
    
    if user.is_verified:
        return {"message": "Email вже підтверджено"}
    
    user.is_verified = True
    db.commit()
    
    return {"message": "Email успішно підтверджено! Тепер ви можете увійти в систему."}

@router.post("/resend-verification")
async def resend_verification(
    email: schemas.EmailStr,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Повторно відправити email для верифікації"""
    
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        # Не розкривати чи існує користувач
        return {"message": "Якщо користувач існує, email буде відправлено"}
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email вже підтверджено"
        )
    
    verification_token = create_email_verification_token(user.email)
    background_tasks.add_task(
        send_verification_email,
        user.email,
        verification_token,
        user.username
    )
    
    return {"message": "Email для підтвердження відправлено"}

@router.post("/forgot-password")
async def forgot_password(
    email: schemas.EmailStr,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Запит на скидання пароля"""
    
    user = db.query(models.User).filter(models.User.email == email).first()
    
    # Не розкривати чи існує користувач
    if user:
        reset_token = create_password_reset_token(user.email)
        background_tasks.add_task(
            send_password_reset_email,
            user.email,
            reset_token,
            user.username
        )
    
    return {"message": "Якщо користувач з таким email існує, інструкції для скидання пароля будуть відправлені"}

@router.post("/reset-password")
async def reset_password(
    reset_data: schemas.PasswordReset,
    db: Session = Depends(get_db)
):
    """Скинути пароль за допомогою токена"""
    
    email = verify_token(reset_data.token, "password_reset")
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невірний або прострочений токен"
        )
    
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Користувач не знайдений"
        )
    
    user.password_hash = get_password_hash(reset_data.new_password)
    db.commit()
    
    return {"message": "Пароль успішно змінено"}

@router.post("/change-password")
async def change_password(
    password_data: schemas.PasswordChange,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Змінити пароль (потрібна аутентифікація)"""
    
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невірний старий пароль"
        )
    
    current_user.password_hash = get_password_hash(password_data.new_password)
    db.commit()
    
    return {"message": "Пароль успішно змінено"}

@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(current_user: models.User = Depends(get_current_user)):
    """Отримати інформацію про поточного користувача"""
    return current_user

@router.put("/me", response_model=schemas.UserResponse)
async def update_current_user(
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Оновити профіль поточного користувача"""
    
    if user_update.username:
        # Перевірити чи username вже використовується
        existing = db.query(models.User).filter(
            models.User.username == user_update.username,
            models.User.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username вже використовується"
            )
        current_user.username = user_update.username
    
    if user_update.email:
        # Перевірити чи email вже використовується
        existing = db.query(models.User).filter(
            models.User.email == user_update.email,
            models.User.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email вже використовується"
            )
        current_user.email = user_update.email
        current_user.is_verified = False  # Потрібна повторна верифікація
    
    db.commit()
    db.refresh(current_user)
    
    return current_user
