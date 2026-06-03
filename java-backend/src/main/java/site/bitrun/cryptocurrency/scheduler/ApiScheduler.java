package site.bitrun.cryptocurrency.scheduler;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.service.CryptoService;
import site.bitrun.cryptocurrency.global.api.upbit.service.UpbitService;

@Slf4j
@Component
public class ApiScheduler {

     // cron 표현식
     // 초(0-59), 분(0-59), 시간(0-23), 일(1-31), 월(1-12), 요일(0-6) (0: 일, 1: 월, 2:화, 3:수, 4:목, 5:금, 6:토)

    private final CryptoService cryptoService;
    private final UpbitService upbitService;

    @Autowired
    public ApiScheduler(CryptoService cryptoService, UpbitService upbitService) {
        this.cryptoService = cryptoService;
        this.upbitService = upbitService;
    }

    // 코인마켓캡 API - 시가총액 top 100 저장 (1시간 마다 실행)
    @Scheduled(cron = "0 0 0/1 * * *", zone = "Asia/Seoul")
    public void saveCoinMarketCapCryptoRank() {
        log.info("saveCoinMarketCapCryptoRank() -> 코인마켓캡 시가총액 Top100 스케쥴러 실행");
        cryptoService.saveCryptoRankList();
    }

    // 업비트 API - 거래가능 market 목록 DB save (오후 6시 1일 1회 업데이트)
    @Scheduled(cron = "0 0 18 * * *", zone = "Asia/Seoul")
    public void saveUpbitMarketDatabase() {
        log.info("saveUpbitMarketDatabase() -> 업비트 거래가능 목록 DB 저장 스케쥴러 실행");
        upbitService.saveUpbitMarket();
    }

    // 업비트 API - 거래가능 market 목록 DB save (이전 작업 종료 후 밀리세컨드 만큼 후 시작 - 1시간)
    /*@Scheduled(fixedDelay = 3600000)
    public void saveUpbitMarketDatabase() {
        log.info("saveUpbitMarketDatabase() -> 업비트 거래가능 목록 DB 저장 스케쥴러 실행");
        upbitService.saveUpbitMarket();
    }*/

}
