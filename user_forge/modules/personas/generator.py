import random
import secrets
import string
import unicodedata
from typing import Optional, List
from faker import Faker

from user_forge.config.settings import settings
from user_forge.core.models import Persona
from user_forge.modules.personas.email_router import EmailRouter

class PersonaGenerator:
    """
    Generates realistic user profiles with es_AR localization,
    coherent bios, secure passwords and valid email routing aliases.
    """
    def __init__(self, locale: Optional[str] = None, email_router: Optional[EmailRouter] = None):
        self.locale = locale or settings.DEFAULT_LOCALE
        self.faker = Faker(self.locale)
        self.email_router = email_router or EmailRouter()

    @staticmethod
    def normalize_string(text: str) -> str:
        # Remove accents/diacritics and special characters for usernames
        nfkd_form = unicodedata.normalize('NFKD', text)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

    @staticmethod
    def generate_secure_password(length: int = 16) -> str:
        """
        Generates compliant 16-character passwords meeting standard complexity requirements
        (uppercase, lowercase, numbers, symbols).
        """
        if length < 12:
            length = 12

        upper = string.ascii_uppercase
        lower = string.ascii_lowercase
        digits = string.digits
        symbols = "!@#$%^&*()_+-="

        # Ensure at least 2 of each class
        password_chars = [
            secrets.choice(upper),
            secrets.choice(upper),
            secrets.choice(lower),
            secrets.choice(lower),
            secrets.choice(digits),
            secrets.choice(digits),
            secrets.choice(symbols),
            secrets.choice(symbols),
        ]

        all_chars = upper + lower + digits + symbols
        for _ in range(length - len(password_chars)):
            password_chars.append(secrets.choice(all_chars))

        secrets.SystemRandom().shuffle(password_chars)
        return "".join(password_chars)

    def generate_username(self, first_name: str, last_name: str) -> str:
        f_norm = self.normalize_string(first_name)
        l_norm = self.normalize_string(last_name)
        rand_num = random.randint(10, 9999)

        patterns = [
            f"{f_norm}.{l_norm}{random.randint(1, 99)}",
            f"{f_norm[0]}{l_norm}{rand_num}",
            f"{f_norm}_{l_norm}",
            f"{l_norm}_{f_norm}",
            f"{f_norm}{l_norm}{rand_num}",
            f"{f_norm}_{rand_num}",
        ]
        return random.choice(patterns)

    def generate_bio(self, role_hint: Optional[str] = None) -> str:
        bios = [
            "Apasionado por la tecnología, el café y la música en vivo.",
            "Desarrollador y creador de contenidos digitales. Siempre aprendiendo cosas nuevas.",
            "Diseño, comunicación y estrategias digitales.",
            "Emprendedor digital, entusiasta del open source y la innovación.",
            "Amante de los viajes, la fotografía urbana y los libros.",
            "Consultor tecnológico enfocado en soluciones ágiles y automatización.",
            "Especialista en proyectos web, optimización y herramientas modernas.",
            "Explorando nuevas fronteras tecnológicas y creando proyectos interesantes.",
            "Creador independiente. Curioso empedernido.",
            "Tech enthusiast, gamer y fanático del cine de ciencia ficción."
        ]
        if role_hint:
            return f"{role_hint}. {random.choice(bios)}"
        return random.choice(bios)

    def generate_one(
        self,
        project_id: Optional[str] = None,
        role_hint: Optional[str] = None,
        email_domain: Optional[str] = None,
        email_strategy: Optional[str] = None
    ) -> Persona:
        # Determine gender for realistic Argentine name pairs
        gender = random.choice(["male", "female"])
        if gender == "male":
            first_name = self.faker.first_name_male()
        else:
            first_name = self.faker.first_name_female()

        last_name = self.faker.last_name()
        full_name = f"{first_name} {last_name}"
        username = self.generate_username(first_name, last_name)

        router = self.email_router
        if email_domain or email_strategy:
            router = EmailRouter(
                domain=email_domain or self.email_router.domain,
                strategy=email_strategy or self.email_router.strategy
            )

        email = router.generate_email(username, project_id=project_id)
        password = self.generate_secure_password(16)
        bio = self.generate_bio(role_hint)
        birth_date = self.faker.date_of_birth(minimum_age=19, maximum_age=65).strftime("%Y-%m-%d")
        phone = self.faker.phone_number()
        city = self.faker.city()

        return Persona(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            username=username,
            email=email,
            password=password,
            bio=bio,
            gender=gender,
            birth_date=birth_date,
            phone=phone,
            city=city,
            country="Argentina",
            metadata={
                "project_id": project_id,
                "role_hint": role_hint,
                "locale": self.locale
            }
        )

    def generate_batch(
        self,
        count: int,
        project_id: Optional[str] = None,
        role_hint: Optional[str] = None,
        email_domain: Optional[str] = None,
        email_strategy: Optional[str] = None
    ) -> List[Persona]:
        return [
            self.generate_one(
                project_id=project_id,
                role_hint=role_hint,
                email_domain=email_domain,
                email_strategy=email_strategy
            )
            for _ in range(count)
        ]
