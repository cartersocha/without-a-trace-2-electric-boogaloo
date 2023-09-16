package k8snetlogreceiver

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/otterize/network-mapper/src/sniffer/pkg/mapperclient"
	"github.com/otterize/network-mapper/src/sniffer/pkg/sniffer"
	"go.opentelemetry.io/collector/component"
	"go.opentelemetry.io/collector/pdata/pcommon"
	"go.opentelemetry.io/collector/pdata/pmetric"
	"go.uber.org/zap"
)

// map of source ip and hostname with dest ips
var ipMap = make(map[string]map[string]bool)

type mapperClient struct {
	logger *zap.Logger
}

func getSrcIpAndHost(srcId string) (string, string) {
	srcIp := ""
	srcHostname := ""
	if len(srcId) > 0 {
		srcIpHostname := strings.Split(srcId, ":")
		if len(srcIpHostname) == 2 {
			srcIp = srcIpHostname[0]
			srcHostname = srcIpHostname[1]
		}
	}
	return srcIp, srcHostname
}

func addToMap(srcIp string, srcHostname string, destIp string) {
	srcId := fmt.Sprintf("%s:%s", srcIp, srcHostname)
	if _, ok := ipMap[srcId]; !ok {
		ipMap[srcId] = make(map[string]bool)
	}
	ipMap[srcId][destIp] = true
}

func (c mapperClient) ReportCaptureResults(ctx context.Context, captureResults mapperclient.CaptureResults) error {
	for _, result := range captureResults.GetResults() {
		for _, dest := range result.Destinations {
			addToMap(result.SrcIp, result.SrcHostname, dest.Destination)
		}
	}
	return nil
}

func (c mapperClient) ReportSocketScanResults(ctx context.Context, socketResults mapperclient.SocketScanResults) error {
	for _, result := range socketResults.GetResults() {
		for _, dest := range result.Destinations {
			addToMap(result.SrcIp, result.SrcHostname, dest.Destination)
		}
	}
	return nil
}

type scraper struct {
	logger      *zap.Logger
	seriesMutex sync.Mutex
	mc          mapperClient
}

func newScraper(logger *zap.Logger) *scraper {
	return &scraper{
		logger: logger,
		mc:     mapperClient{logger: logger},
	}
}

func (s *scraper) scrape(ctx context.Context) (pmetric.Metrics, error) {
	m := pmetric.NewMetrics()

	// Obtain write lock to reset data
	s.seriesMutex.Lock()
	defer s.seriesMutex.Unlock()

	for srcId, destIps := range ipMap {
		for destIp := range destIps {
			srcIp, srcHostname := getSrcIpAndHost(srcId)

			rm := m.ResourceMetrics().AppendEmpty()
			rm.Resource().Attributes().PutStr("client.socket.address", srcIp)
			rm.Resource().Attributes().PutStr("client.address", srcHostname)
			rm.Resource().Attributes().PutStr("server.socket.address", destIp)

			ilm := rm.ScopeMetrics().AppendEmpty()
			ilm.Scope().SetName("traces_service_graph")
			mCount := ilm.Metrics().AppendEmpty()

			// use metric format compatible with grafana service graph visualization
			mCount.SetName("traces_service_graph_request_total_test0")
			mCount.SetEmptySum().SetIsMonotonic(true)
			mCount.Sum().SetAggregationTemporality(pmetric.AggregationTemporalityCumulative)

			dpCalls := mCount.Sum().DataPoints().AppendEmpty()
			dpCalls.SetStartTimestamp(pcommon.NewTimestampFromTime(time.Now()))
			dpCalls.SetTimestamp(pcommon.NewTimestampFromTime(time.Now()))
			dpCalls.SetIntValue(1)

			dims := pcommon.NewMap()
			dims.PutStr("client", srcIp)
			dims.PutStr("server", destIp)
			dims.CopyTo(dpCalls.Attributes())
		}
	}

	return m, nil
}

func (s *scraper) start(context.Context, component.Host) error {
	s.logger.Debug("starting scraper with network sniffer...")
	snifferInstance := sniffer.NewSniffer(s.mc)

	go func() {
		err := snifferInstance.RunForever(context.Background())
		if err != nil {
			panic(err)
		}
	}()

	return nil
}
