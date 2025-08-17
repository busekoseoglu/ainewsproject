# news/views.py (FİLTRELEMELİ YENİ VERSİYON)

from django.shortcuts import render
from .models import News
from datetime import datetime, timedelta
from django.utils import timezone # Zaman dilimi için bu modülü ekliyoruz

def news_list(request):
    # Başlangıçta tüm haberleri tarihe göre sıralayarak alıyoruz
    news_query = News.objects.all().order_by('-published')
    
    # Filtreleme için GET parametrelerini alıyoruz
    selected_sources = request.GET.getlist('source')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Kaynak filtresi (Tekil kaynak seçimi için 'get' kullanmak daha uygun olabilir)
    # Eğer birden çok kaynak seçme ihtimalini gelecekte istersen 'getlist' kalabilir.
    # Şimdiki dropdown tekil seçim yaptığı için 'get' kullanıyorum.
    selected_source = request.GET.get('source')
    if selected_source:
        news_query = news_query.filter(source=selected_source)

    # Tarih filtresi - DÜZELTİLMİŞ BÖLÜM
    if start_date_str and end_date_str:
        try:
            # Gelen string'leri datetime nesnesine çeviriyoruz
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

            # Bitiş tarihini gün sonu (23:59:59) yapıyoruz ki o günkü haberler de dahil olsun
            end_date = end_date + timedelta(days=1, seconds=-1)

            # "Naive" datetime nesnelerini "Aware" (zaman dilimine duyarlı) hale getiriyoruz
            # Bu işlem, settings.py'deki TIME_ZONE'u kullanır.
            start_date = timezone.make_aware(start_date)
            end_date = timezone.make_aware(end_date)
            
            # Veritabanında sorguyu yapıyoruz
            news_query = news_query.filter(published__range=(start_date, end_date))
        except (ValueError, TypeError):
            # Eğer tarih formatı bozuksa veya boşsa bu adımı atla
            pass

    # Kenar çubuğundaki filtre listesi için tüm kaynakları al
    # distinct() ile her kaynak isminin sadece bir kere listelenmesini sağlıyoruz
    all_sources = News.objects.values_list('source', flat=True).distinct().order_by('source')

    context = {
        'news_list': news_query,
        'all_sources': all_sources,
        'selected_sources': [selected_source] if selected_source else [], # Şablonun hata vermemesi için
        'start_date': start_date_str, # Seçilen değerleri template'e geri gönderiyoruz
        'end_date': end_date_str,
    }
    return render(request, 'news/news_list.html', context)