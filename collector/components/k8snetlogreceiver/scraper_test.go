package k8snetlogreceiver

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"go.uber.org/zap"
	"go.uber.org/zap/zaptest"
)

func TestNewScraper(t *testing.T) {
	logger := zap.NewNop()
	s := newScraper(logger)

	assert.NotNil(t, s)
	assert.Equal(t, s.logger, logger)
}

func TestScrape(t *testing.T) {
	logger := zaptest.NewLogger(t)

	s := newScraper(logger)

	ctx := context.Background()
	metrics, err := s.scrape(ctx)

	assert.NotNil(t, metrics)
	assert.Nil(t, err)
}
