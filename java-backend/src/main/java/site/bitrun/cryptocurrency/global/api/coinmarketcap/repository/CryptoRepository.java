package site.bitrun.cryptocurrency.global.api.coinmarketcap.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.transaction.annotation.Transactional;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.domain.CryptoRank;

public interface CryptoRepository extends JpaRepository<CryptoRank, Long> {

    @Transactional
    @Modifying
    @Query(value = "truncate table crypto_rank", nativeQuery = true)
    void truncateCryptoRankTable();
}
