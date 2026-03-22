import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { getTopicGraph } from '../api';

export default function TopicGraph({ onCategoryClick }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [data, setData] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);

  useEffect(() => {
    getTopicGraph(15, 3).then(setData).catch(console.error);
  }, []);

  useEffect(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 600;

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height]);

    // Color scale based on count
    const maxCount = d3.max(data.nodes, (d) => d.count) || 1;
    const colorScale = d3.scaleSequential(d3.interpolateBlues)
      .domain([0, maxCount]);

    // Size scale
    const sizeScale = d3.scaleSqrt()
      .domain([0, maxCount])
      .range([6, 45]);

    // Link weight scale
    const maxWeight = d3.max(data.links, (d) => d.weight) || 1;
    const linkScale = d3.scaleLinear()
      .domain([0, maxWeight])
      .range([0.3, 3]);

    const linkOpacityScale = d3.scaleLinear()
      .domain([0, maxWeight])
      .range([0.08, 0.4]);

    // Force simulation
    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.links).id((d) => d.id).distance(120).strength(0.3))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d) => sizeScale(d.count) + 8));

    // Container for zoom
    const g = svg.append('g');

    // Zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.3, 4])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(data.links)
      .join('line')
      .attr('stroke', '#94a3b8')
      .attr('stroke-width', (d) => linkScale(d.weight))
      .attr('stroke-opacity', (d) => linkOpacityScale(d.weight));

    // Nodes group
    const node = g.append('g')
      .selectAll('g')
      .data(data.nodes)
      .join('g')
      .style('cursor', 'pointer')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }));

    // Node circles
    node.append('circle')
      .attr('r', (d) => sizeScale(d.count))
      .attr('fill', (d) => colorScale(d.count))
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
      .on('mouseover', function (event, d) {
        d3.select(this).attr('stroke', '#4f46e5').attr('stroke-width', 3);
        setHoveredNode(d);
      })
      .on('mouseout', function () {
        d3.select(this).attr('stroke', '#fff').attr('stroke-width', 1.5);
        setHoveredNode(null);
      })
      .on('click', (event, d) => {
        if (onCategoryClick) onCategoryClick(d.id);
      });

    // Labels (only for nodes with count > threshold)
    const labelThreshold = d3.quantile(data.nodes.map((d) => d.count).sort(d3.ascending), 0.4) || 30;
    node.filter((d) => d.count >= labelThreshold)
      .append('text')
      .text((d) => d.id)
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => sizeScale(d.count) + 14)
      .attr('font-size', (d) => Math.max(9, Math.min(13, d.count / 50 + 8)))
      .attr('fill', '#374151')
      .attr('pointer-events', 'none');

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y);

      node.attr('transform', (d) => `translate(${d.x},${d.y})`);
    });

    return () => simulation.stop();
  }, [data, onCategoryClick]);

  if (!data) return <div className="text-center py-12 text-gray-400">Chargement du graphe...</div>;

  return (
    <div ref={containerRef} className="relative bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-800">Carte des thématiques</h3>
        <span className="text-xs text-gray-400">{data.nodes.length} thèmes — cliquez pour explorer, glissez pour déplacer</span>
      </div>
      <svg ref={svgRef} className="w-full" />
      {hoveredNode && (
        <div className="absolute bottom-4 left-4 bg-white/95 backdrop-blur rounded-lg shadow-lg px-4 py-2 border border-gray-200">
          <span className="text-sm font-semibold text-gray-800">{hoveredNode.id}</span>
          <span className="ml-2 text-xs text-gray-500">{hoveredNode.count} items</span>
        </div>
      )}
    </div>
  );
}
