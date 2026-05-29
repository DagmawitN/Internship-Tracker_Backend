from django.urls import path
from .views import (
    AskQuestionView,
    CVAnalysisView,
    IndexKnowledgeBaseView,
    InternshipRecommendView,
)

urlpatterns = [
    path("ask/", AskQuestionView.as_view(), name="assistant-ask"),
    path("cv/", CVAnalysisView.as_view(), name="assistant-cv"),
    path("index/", IndexKnowledgeBaseView.as_view(), name="assistant-index"),
    path("recommend/", InternshipRecommendView.as_view(), name="assistant-recommend"),
]
