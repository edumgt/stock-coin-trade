package site.bitrun.cryptocurrency.global.api.upbit.service;

import site.bitrun.cryptocurrency.global.api.upbit.domain.UpbitMarket;

import java.util.List;

public interface UpbitService {

    void saveUpbitMarket(); // 업비트 마켓 list DB save

    List<UpbitMarket> getUpbitMarketList();

    UpbitMarket getUpbitMarketOne(String code);
}
