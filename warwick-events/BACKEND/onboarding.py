"""Student preferences and deterministic society matching; no AI calls."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

CATALOG_DIR = Path(__file__).resolve().parent / 'catalogs'
CATALOGS = {name: json.loads((CATALOG_DIR / f'{name}.json').read_text(encoding='utf-8'))
            for name in ('courses', 'interests', 'societies')}
COURSES = {item['id']: item for item in CATALOGS['courses']['items']}
SOCIETIES = {item['id']: item for item in CATALOGS['societies']['items']}
INTEREST_CATEGORIES = {interest['id']: group['event_category']
                       for group in CATALOGS['interests']['items'] for interest in group['interests']}


class StudentProfile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    course_id: str | None = None
    graduation_year: int | None = Field(None, strict=True)
    ethnicity: str | None = Field(None, max_length=100)
    cultural_recommendations_opt_in: bool = False
    interest_ids: list[str] = Field(default_factory=list, max_length=200)
    followed_society_ids: list[str] = Field(default_factory=list, max_length=200)
    step: int = Field(1, ge=1, le=4, strict=True)
    onboarding_completed: bool = False


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    course_id: str | None = None
    graduation_year: int | None = Field(None, strict=True)
    ethnicity: str | None = Field(None, max_length=100)
    cultural_recommendations_opt_in: bool = False
    interest_ids: list[str] = Field(default_factory=list, max_length=200)
    followed_society_ids: list[str] = Field(default_factory=list, max_length=200)
    step: int = Field(1, ge=1, le=4, strict=True)
    onboarding_completed: bool = False


def read_profile(rows, email):
    found = rows('SELECT body FROM student_profiles WHERE email=?', (email,))
    return StudentProfile.model_validate_json(found[0][0]) if found else StudentProfile()


def profile_response(profile):
    return {**profile.model_dump(), 'event_categories': sorted({INTEREST_CATEGORIES[i]
            for i in profile.interest_ids if i in INTEREST_CATEGORIES})}


def matching_societies(profile):
    course = COURSES.get(profile.course_id, {})
    matches = []
    for society in SOCIETIES.values():
        interests = sorted(set(profile.interest_ids) & set(society['interest_ids']))
        course_match = course.get('subject') in society['course_subjects']
        score = 2 * len(interests) + int(course_match)
        if score:
            matches.append({**society, 'matching_interest_ids': interests,
                            'course_match': course_match, 'score': score,
                            'followed': society['id'] in profile.followed_society_ids})
    return sorted(matches, key=lambda item: (-item['score'], item['name'].casefold(), item['id']))


def register_onboarding(router, identity, rows, write, lock):
    def student(user=Depends(identity)):
        if user['role'] != 'student':
            raise HTTPException(403, 'student account required')
        return user

    @router.get('/profile')
    def get_profile(user=Depends(student)):
        return profile_response(read_profile(rows, user['email']))

    @router.put('/profile')
    def update_profile(payload: ProfileUpdate, user=Depends(student)):
        with lock:
            data = read_profile(rows, user['email']).model_dump()
            data.update(payload.model_dump(exclude_unset=True))
            try:
                profile = StudentProfile.model_validate(data)
            except ValueError:
                raise HTTPException(422, 'Invalid profile fields') from None
            year = datetime.now(ZoneInfo('Europe/London')).year
            if profile.graduation_year is not None and not year <= profile.graduation_year <= year + 10:
                raise HTTPException(422, f'Graduation year must be between {year} and {year + 10}')
            if profile.course_id is not None and profile.course_id not in COURSES and profile.course_id != 'not-listed':
                raise HTTPException(422, 'Choose a listed course or Course not listed')
            if not set(profile.interest_ids).issubset(INTEREST_CATEGORIES):
                raise HTTPException(422, 'Unknown interest')
            if not set(profile.followed_society_ids).issubset(SOCIETIES):
                raise HTTPException(422, 'Unknown society')
            profile.interest_ids = list(dict.fromkeys(profile.interest_ids))
            profile.followed_society_ids = list(dict.fromkeys(profile.followed_society_ids))
            profile.ethnicity = profile.ethnicity.strip() or None if profile.ethnicity else None
            if profile.onboarding_completed and (not profile.course_id or profile.graduation_year is None):
                raise HTTPException(422, 'Choose your course and graduation year before completing onboarding')
            write('INSERT OR REPLACE INTO student_profiles VALUES(?,?)',
                  (user['email'], profile.model_dump_json()))
        return profile_response(profile)

    @router.get('/courses')
    def courses(user=Depends(identity)):
        year = datetime.now(ZoneInfo('Europe/London')).year
        return {**CATALOGS['courses'], 'graduation_years': list(range(year, year + 11)),
                'items': CATALOGS['courses']['items'] + [{'id': 'not-listed', 'name': 'Course not listed',
                                                        'subject': None, 'source_url': None}]}

    @router.get('/interests')
    def interests(user=Depends(identity)):
        return CATALOGS['interests']

    @router.get('/societies/matches')
    def matches(user=Depends(student)):
        return matching_societies(read_profile(rows, user['email']))

    @router.get('/societies')
    def societies(user=Depends(identity)):
        return CATALOGS['societies']
