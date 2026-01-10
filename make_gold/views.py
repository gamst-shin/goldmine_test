from django.shortcuts import render
from django.db.models import Q
from .models import AuctionItem

def gold_list(request):
    # 1. 기본: 모든 데이터 가져오기 (최신순)
    items = AuctionItem.objects.all().order_by('-created_at')

    # 2. 검색어 처리 (Search)
    # GET 파라미터 'q'를 받음 (예: ?q=24k)
    query = request.GET.get('q', '')
    if query:
        # 제목이나 설명에 검색어가 포함된 경우 필터링 (OR 조건)
        items = items.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query)
        )

    # 3. 지역 필터링 (Filter)
    # GET 파라미터 'region'을 받음 (예: ?region=서울)
    region = request.GET.get('region', '')
    if region:
        items = items.filter(location__icontains=region)

    # 4. 템플릿에 전달할 데이터 패키징
    context = {
        'items': items,
        'query': query,
        'region': region,
        'total_count': items.count(),
    }

    return render(request, 'make_gold/index.html', context)