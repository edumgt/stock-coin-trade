package site.bitrun.cryptocurrency.global.api.upbit.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import site.bitrun.cryptocurrency.global.api.upbit.domain.UpbitMarket;
import site.bitrun.cryptocurrency.global.api.upbit.dto.UpbitMarketDto;

import java.util.List;

public interface UpbitRepository extends JpaRepository<UpbitMarket, Long> {
    List<UpbitMarket> findByMarketLike(String market);

    UpbitMarket findByMarket(String code);
}
