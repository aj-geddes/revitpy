import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Filter, TrendingUp, Download, Star, Calendar, Package, Tag } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import { PackageCard } from '@/components/package-card';
import { PackageFilters } from '@/components/package-filters';
import { PaginatedList } from '@/components/paginated-list';
import { usePackageSearch } from '@/hooks/use-package-search';
import type { PackageSearchQuery } from '@revitpy/types';

export default function PackageRegistryHome() {
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<Omit<PackageSearchQuery, 'query'>>({
    sortBy: 'downloads',
    sortOrder: 'desc',
    limit: 20,
    offset: 0
  });

  const {
    data: searchResults,
    isLoading,
    isError,
    error
  } = usePackageSearch({
    query: searchQuery,
    ...filters
  });

  const { data: featuredPackages } = useQuery({
    queryKey: ['packages', 'featured'],
    queryFn: async () => {
      // Mock featured packages - replace with actual API call
      return [
        {
          id: 'revitpy-walls',
          name: 'revitpy-walls',
          version: '1.2.0',
          description: 'Advanced wall manipulation tools for Revit',
          author: 'RevitPy Team',
          category: 'modeling',
          tags: ['walls', 'modeling', 'geometry'],
          rating: 4.8,
          downloadCount: 15420,
          publishDate: new Date('2024-01-15'),
          revitVersions: ['2022', '2023', '2024'],
          verified: true
        },
        {
          id: 'data-export-toolkit',
          name: 'data-export-toolkit',
          version: '2.1.3',
          description: 'Export Revit model data to various formats (Excel, JSON, CSV)',
          author: 'DataTools Inc',
          category: 'export',
          tags: ['export', 'data', 'excel', 'csv'],
          rating: 4.6,
          downloadCount: 8920,
          publishDate: new Date('2024-01-20'),
          revitVersions: ['2021', '2022', '2023', '2024'],
          verified: true
        },
        {
          id: 'schedule-automation',
          name: 'schedule-automation',
          version: '1.0.8',
          description: 'Automate schedule creation and management',
          author: 'AutoSchedule',
          category: 'automation',
          tags: ['schedules', 'automation', 'reports'],
          rating: 4.4,
          downloadCount: 5680,
          publishDate: new Date('2024-02-01'),
          revitVersions: ['2023', '2024'],
          verified: false
        }
      ];
    }
  });

  const { data: stats } = useQuery({
    queryKey: ['packages', 'stats'],
    queryFn: async () => ({
      totalPackages: 1247,
      totalDownloads: 156890,
      activeAuthors: 432,
      categories: [
        { name: 'Modeling', count: 287 },
        { name: 'Export/Import', count: 198 },
        { name: 'Automation', count: 156 },
        { name: 'Analysis', count: 134 },
        { name: 'Visualization', count: 89 },
        { name: 'Utilities', count: 246 }
      ]
    })
  });

  const handleSearch = (value: string) => {
    setSearchQuery(value);
    setFilters(prev => ({ ...prev, offset: 0 }));
  };

  const handleFiltersChange = (newFilters: Partial<PackageSearchQuery>) => {
    setFilters(prev => ({ ...prev, ...newFilters, offset: 0 }));
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold tracking-tight">RevitPy Package Registry</h1>
        <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
          Discover, install, and share Python packages for Revit development.
          Extend your BIM workflows with community-driven tools and libraries.
        </p>
      </div>

      {/* Search Bar */}
      <div className="max-w-2xl mx-auto">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search packages..."
            className="pl-10 h-12 text-lg"
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold">{stats.totalPackages.toLocaleString()}</div>
              <div className="text-sm text-muted-foreground">Total Packages</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold">{stats.totalDownloads.toLocaleString()}</div>
              <div className="text-sm text-muted-foreground">Total Downloads</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold">{stats.activeAuthors.toLocaleString()}</div>
              <div className="text-sm text-muted-foreground">Active Authors</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold">24/7</div>
              <div className="text-sm text-muted-foreground">Support Available</div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="browse" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="browse">Browse Packages</TabsTrigger>
          <TabsTrigger value="featured">Featured</TabsTrigger>
          <TabsTrigger value="categories">Categories</TabsTrigger>
        </TabsList>

        {/* Browse Packages Tab */}
        <TabsContent value="browse" className="space-y-6">
          <div className="flex flex-col lg:flex-row gap-6">
            {/* Filters Sidebar */}
            <div className="lg:w-64 flex-shrink-0">
              <PackageFilters
                filters={filters}
                onFiltersChange={handleFiltersChange}
                facets={searchResults?.facets}
              />
            </div>

            {/* Package Results */}
            <div className="flex-1">
              {isLoading && (
                <div className="text-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
                  <p>Searching packages...</p>
                </div>
              )}

              {isError && (
                <div className="text-center py-12">
                  <p className="text-red-500">Error loading packages: {error?.message}</p>
                  <Button
                    variant="outline"
                    className="mt-4"
                    onClick={() => window.location.reload()}
                  >
                    Retry
                  </Button>
                </div>
              )}

              {searchResults && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <p className="text-muted-foreground">
                      {searchResults.total.toLocaleString()} packages found
                      {searchQuery && ` for "${searchQuery}"`}
                    </p>

                    <Select
                      value={`${filters.sortBy}-${filters.sortOrder}`}
                      onValueChange={(value) => {
                        const [sortBy, sortOrder] = value.split('-') as [string, 'asc' | 'desc'];
                        handleFiltersChange({ sortBy, sortOrder });
                      }}
                    >
                      <SelectTrigger className="w-48">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="downloads-desc">Most Downloaded</SelectItem>
                        <SelectItem value="rating-desc">Highest Rated</SelectItem>
                        <SelectItem value="updated-desc">Recently Updated</SelectItem>
                        <SelectItem value="created-desc">Newest</SelectItem>
                        <SelectItem value="name-asc">Name A-Z</SelectItem>
                        <SelectItem value="name-desc">Name Z-A</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <PaginatedList
                    items={searchResults.results}
                    total={searchResults.total}
                    pageSize={filters.limit || 20}
                    currentPage={Math.floor((filters.offset || 0) / (filters.limit || 20))}
                    onPageChange={(page) => {
                      handleFiltersChange({ offset: page * (filters.limit || 20) });
                    }}
                    renderItem={(item) => <PackageCard key={item.id} package={item} />}
                  />
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* Featured Packages Tab */}
        <TabsContent value="featured" className="space-y-6">
          <div>
            <h2 className="text-2xl font-bold mb-4">Featured Packages</h2>
            <p className="text-muted-foreground mb-6">
              Hand-picked packages that showcase the best of RevitPy development
            </p>
          </div>

          {featuredPackages && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {featuredPackages.map((pkg) => (
                <PackageCard key={pkg.id} package={pkg} featured />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Categories Tab */}
        <TabsContent value="categories" className="space-y-6">
          <div>
            <h2 className="text-2xl font-bold mb-4">Browse by Category</h2>
            <p className="text-muted-foreground mb-6">
              Explore packages organized by functionality and use case
            </p>
          </div>

          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {stats.categories.map((category) => (
                <Card
                  key={category.name}
                  className="cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => {
                    handleFiltersChange({ category: category.name.toLowerCase() });
                    // Switch to browse tab
                    const tabsTrigger = document.querySelector('[value=\"browse\"]') as HTMLElement;
                    tabsTrigger?.click();
                  }}
                >
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center justify-between">
                      <span>{category.name}</span>
                      <Badge variant="secondary">{category.count}</Badge>
                    </CardTitle>
                  </CardHeader>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
