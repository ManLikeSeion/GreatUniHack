"""Explainable concept expansion and relevance ranking for campus events."""
import re

CONCEPTS = {
    'travel': ['travel', 'trip', 'trips', 'bus', 'coach', 'excursion', 'tour', 'tours', 'away day', 'away match', 'abroad', 'getaway', 'transport', 'journey', 'hike', 'hiking', 'lost'],
    'food': ['food', 'pizza', 'meal', 'dinner', 'lunch', 'breakfast', 'brunch', 'bake', 'baking', 'cooking', 'potluck', 'snacks'],
    'music': ['music', 'concert', 'gig', 'band', 'choir', 'singing', 'karaoke', 'orchestra', 'jazz', 'dj'],
    'sport': ['sport', 'sports', 'football', 'badminton', 'darts', 'hockey', 'rugby', 'tennis', 'basketball', 'fitness', 'training'],
    'career': ['career', 'careers', 'networking', 'internship', 'recruitment', 'employer', 'industry', 'professional'],
    'art': ['art', 'arts', 'painting', 'drawing', 'craft', 'crafts', 'pottery', 'exhibition', 'creative'],
    'film': ['film', 'films', 'cinema', 'movie', 'movies', 'screening'],
    'social': ['social', 'socials', 'meetup', 'mixer', 'party', 'pub', 'club', 'nightlife', 'games night'],
}
STOP = set('a an the i me my we us you your find show recommend recommendations looking for want would like please events event something anything some all any upcoming today tomorrow on at in of to and or with without no clash clashes free food this that there are is be can could do does not doesn t don only available plans saved same but instead more'.split())


def words(text):
    return re.findall(r'[a-z]+', text.lower())


def terms_for(message, ai_terms=None):
    # Dates and constraint wording are not topical search terms.
    text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '', message.lower())
    direct = {word for word in words(text) if word not in STOP and len(word) > 1}
    # AI can supplement a query with a small set of synonyms, never event IDs.
    related = set()
    for term in ai_terms or []:
        related.update(word for word in words(term) if word not in STOP)
    for concept, synonyms in CONCEPTS.items():
        if any(term in direct for term in [concept, *synonyms]):
            related.update([concept, *synonyms])
    return direct, related - direct


def relevance(event, direct, related):
    score = 0
    evidence = []
    for field, weight in [('title', 6), ('society', 4), ('description', 2), ('location', 1), ('category', 2)]:
        text = str(event.get(field) or '').lower()
        for term in direct | related:
            # Word boundaries prevent "bus" matching unrelated substrings.
            if re.search(r'\b' + re.escape(term) + r'(?:s)?\b', text):
                score += weight * (3 if term in direct else 1)
                if term not in evidence:
                    evidence.append(term)
    return score, evidence
