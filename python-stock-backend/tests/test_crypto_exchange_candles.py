from unittest.mock import Mock, patch
import pytest
from app.services import crypto_exchanges as market
from app.services.brokers.common import BrokerApiError

def response(data):
 r=Mock(ok=True,status_code=200);r.json.return_value=data;return r

@patch('app.services.crypto_exchanges.requests.get')
def test_binance_ohlcv_sorted_deduplicated(get):
 get.return_value=response([[200000,2,4,1,3,5],[100000,1,3,1,2,4],[100000,1,3,1,2,6]])
 d=market.get_exchange_candles('binance','BTCUSDT')
 assert [r['time'] for r in d['candles']]==[100,200]
 assert d['candles'][0]['volume']==6
 assert get.call_args.kwargs['params']['interval']=='1h'

@patch('app.services.crypto_exchanges.requests.get')
def test_korbit_interval_mapping(get):
 get.return_value=response({'success':True,'data':[{'timestamp':200000,'open':'2','high':'4','low':'1','close':'3','volume':'5'}]})
 assert market.get_exchange_candles('korbit','btc_krw','1d')['candles'][0]['close']==3
 assert get.call_args.kwargs['params']['interval']=='1D'

@patch('app.services.crypto_exchanges.requests.get')
def test_rejects_nonfinite_prices(get):
 get.return_value=response([[100000,'NaN',4,1,3,5]])
 with pytest.raises(BrokerApiError):market.get_exchange_candles('binance','BTCUSDT')

@pytest.mark.parametrize('path',['/binance/candles?symbol=BTCUSDT&interval=bad','/korbit/candles?symbol=bad','/unknown/candles?symbol=BTCUSDT'])
@patch('app.services.crypto_exchanges.requests.get')
def test_invalid_requests_do_not_call_exchange(get,client,path):
 assert client.get('/api/crypto-exchange-test'+path).json()['ok'] is False
 get.assert_not_called()

@patch('app.services.crypto_exchanges.requests.get')
def test_candle_limit_is_bounded(get,client):
 assert client.get('/api/crypto-exchange-test/binance/candles?symbol=BTCUSDT&limit=201').status_code==400
 get.assert_not_called()
