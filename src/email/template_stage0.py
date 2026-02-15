from dataclasses import dataclass
from pathlib import Path


@dataclass
class EmailDraft:
    subject: str
    body: str
    attachments: list[Path]


_SUBJECT = "FlexiHome \u2013 komplet ofert i dokumentacja techniczna"

_BODY_TEMPLATE = """\
{greeting}

Dziękujemy za kontakt i zainteresowanie domami modułowymi FlexiHome.

Zakup domu to decyzja na lata \u2013 dlatego stawiamy na pełną przejrzystość i konkrety już na etapie pierwszego kontaktu.

W załączeniu przesyłam 3 oferty zawierające szczegółowe informacje dotyczące naszych modeli domów wraz z zakresem realizacji.

Każdy dom realizujemy w standardzie \u201epod klucz\u201d (bez mebli ruchomych), co oznacza, że otrzymują Państwo w pełni wykończony, gotowy do zamieszkania budynek \u2013 bez ukrytych kosztów i niedomówień.

Nasza technologia oparta jest na rozwiązaniach zapewniających trwałość, komfort i zdrowy mikroklimat wewnętrzny:
\u2013 dyfuzja pary wodnej i oddychająca konstrukcja ścian,
\u2013 certyfikowane materiały konstrukcyjne wysokiej jakości,
\u2013 podwyższona akustyka przegród,
\u2013 kontrola wilgotności i stabilność parametrów powietrza,
\u2013 wysoka bezwładność cieplna poprawiająca efektywność energetyczną.

W dokumentacji znajdą Państwo:
\u2013 dokładny zakres prac,
\u2013 specyfikację materiałową,
\u2013 parametry techniczne,
\u2013 warunki współpracy.

Jeśli chcieliby Państwo omówić szczegóły oraz dopasować model do swoich potrzeb, zapraszam do bezpośredniej rezerwacji rozmowy w kalendarzu:

{calendar_url}

To jedyna forma umawiania konsultacji \u2013 po wybraniu terminu otrzymają Państwo automatyczne potwierdzenie spotkania.

Pozostaję do dyspozycji.
Z wyrazami szacunku,
Zespół FlexiHome
"""


def build_stage0_email(
    *,
    calendar_url: str,
    greeting: str = "Dzień dobry,",
    attachments: list[Path],
) -> EmailDraft:
    if not calendar_url:
        raise ValueError("calendar_url must not be empty")
    if len(attachments) != 3:
        raise ValueError(f"Expected exactly 3 attachments, got {len(attachments)}")

    body = _BODY_TEMPLATE.format(greeting=greeting, calendar_url=calendar_url)
    return EmailDraft(subject=_SUBJECT, body=body, attachments=list(attachments))
