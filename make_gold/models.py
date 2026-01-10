from django.db import models

class AuctionItem(models.Model):
    # 1. 식별자 (URL을 ID로)
    url = models.URLField(max_length=500, unique=True, verbose_name="상세페이지 URL")

    # 2. 리스트 정보
    image_url = models.URLField(max_length=500, null=True, blank=True, verbose_name="썸네일 URL")
    title = models.CharField(max_length=255, verbose_name="물품명")
    location = models.CharField(max_length=100, verbose_name="보관장소/지역")
    price = models.BigIntegerField(default=0, verbose_name="최저입찰가")

    # 3. 상세 정보
    description = models.TextField(blank=True, verbose_name="물품 상세설명")
    
    # 4. 메타 데이터
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="수집일시")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="갱신일시")

    def __str__(self):
        return f"[{self.location}] {self.title}"

    class Meta:
        db_table = 'gold_items' # 테이블 이름도 'gold_items'로 센스 있게 바꿨다
        ordering = ['-created_at']