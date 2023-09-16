package k8snetlogreceiver

import (
	"context"
	"errors"

	"go.opentelemetry.io/collector/component"
	"go.opentelemetry.io/collector/consumer"
	"go.opentelemetry.io/collector/receiver"
	"go.opentelemetry.io/collector/receiver/scraperhelper"

	"go.uber.org/zap"
)

const (
	typeStr = "k8snetlogreceiver"
)

var errInvalidConfig = errors.New("invalid config for tcpstatsreceiver")

type Config struct {
	scraperhelper.ScraperControllerSettings `mapstructure:",squash"` // ScraperControllerSettings to configure scraping interval (default: 10s)
}

func createDefaultConfig() component.Config {
	return &Config{
		ScraperControllerSettings: scraperhelper.ScraperControllerSettings{
			CollectionInterval: 10,
		},
	}
}

func NewFactory() receiver.Factory {
	return receiver.NewFactory(
		typeStr,
		createDefaultConfig,
		receiver.WithMetrics(createMetrics, component.StabilityLevelDevelopment),
	)
}

func createMetrics(
	_ context.Context,
	set receiver.CreateSettings,
	cfg component.Config,
	consumer consumer.Metrics,
) (receiver.Metrics, error) {
	nlCfg, ok := cfg.(*Config)
	if !ok {
		return nil, errInvalidConfig
	}

	ns := newScraper(set.Logger)
	scraper, err := scraperhelper.NewScraper("myscraper", ns.scrape, scraperhelper.WithStart(ns.start))
	if err != nil {
		set.Logger.Error("Failed to create new scraper helper", zap.Error(err))
		return nil, err
	}

	return scraperhelper.NewScraperControllerReceiver(
		&nlCfg.ScraperControllerSettings,
		set,
		consumer,
		scraperhelper.AddScraper(scraper))
}
