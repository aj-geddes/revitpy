import { useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  Download, 
  Star, 
  Calendar, 
  User, 
  Shield, 
  Package, 
  ExternalLink,
  Heart,
  BookOpen,
  Code
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { PackageSearchResult } from '@revitpy/types';

interface PackageCardProps {
  package: PackageSearchResult;
  featured?: boolean;
  compact?: boolean;
}

export function PackageCard({ package: pkg, featured = false, compact = false }: PackageCardProps) {
  const [isInstalling, setIsInstalling] = useState(false);
  const [isFavorited, setIsFavorited] = useState(false);

  const handleInstall = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    setIsInstalling(true);
    try {
      // Mock installation - replace with actual API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      // Show success notification
    } catch (error) {
      // Show error notification
    } finally {
      setIsInstalling(false);
    }
  };

  const handleFavorite = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsFavorited(!isFavorited);
  };

  const CardComponent = compact ? 'div' : Card;
  const cardProps = compact ? { className: 'border rounded-lg p-4' } : {};

  return (
    <CardComponent {...cardProps}>
      <Link to={`/packages/${pkg.id}`} className="block">
        <div className={cn('space-y-4', compact && 'space-y-2')}>
          {/* Header */}
          <div className="flex items-start justify-between">
            <div className="flex items-start space-x-3 flex-1 min-w-0">
              {/* Package Icon */}
              <div className={cn(
                'flex-shrink-0 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center',
                compact ? 'w-10 h-10' : 'w-12 h-12'
              )}>
                <Package className={cn('text-primary', compact ? 'h-5 w-5' : 'h-6 w-6')} />
              </div>

              {/* Package Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2 mb-1">
                  <h3 className={cn(
                    'font-semibold truncate',
                    compact ? 'text-base' : 'text-lg'
                  )}>
                    {pkg.name}
                  </h3>
                  
                  {featured && (
                    <Badge variant="secondary" className="shrink-0">
                      <Star className="h-3 w-3 mr-1 fill-current" />
                      Featured
                    </Badge>
                  )}
                  
                  {pkg.verified && (
                    <Tooltip>
                      <TooltipTrigger>
                        <Shield className="h-4 w-4 text-green-500" />
                      </TooltipTrigger>
                      <TooltipContent>Verified package</TooltipContent>
                    </Tooltip>
                  )}
                </div>

                <p className={cn(
                  'text-muted-foreground line-clamp-2',
                  compact ? 'text-sm' : 'text-sm'
                )}>
                  {pkg.description}
                </p>

                {/* Author and Version */}
                <div className="flex items-center space-x-4 mt-2">
                  <div className="flex items-center space-x-1 text-xs text-muted-foreground">
                    <User className="h-3 w-3" />
                    <span>{pkg.author}</span>
                  </div>
                  
                  <Badge variant="outline" className="text-xs">
                    v{pkg.version}
                  </Badge>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center space-x-2 ml-4">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={handleFavorite}
              >
                <Heart className={cn(
                  'h-4 w-4',
                  isFavorited && 'fill-current text-red-500'
                )} />
              </Button>

              <Button
                size={compact ? 'sm' : 'default'}
                onClick={handleInstall}
                disabled={isInstalling}
                className="shrink-0"
              >
                {isInstalling ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current" />
                ) : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    Install
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Tags */}
          {!compact && pkg.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {pkg.tags.slice(0, 4).map((tag) => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
              {pkg.tags.length > 4 && (
                <Badge variant="secondary" className="text-xs">
                  +{pkg.tags.length - 4}
                </Badge>
              )}
            </div>
          )}

          {/* Stats and Metadata */}
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <div className="flex items-center space-x-4">
              {/* Downloads */}
              <div className="flex items-center space-x-1">
                <Download className="h-3 w-3" />
                <span>{pkg.downloadCount.toLocaleString()}</span>
              </div>

              {/* Rating */}
              <div className="flex items-center space-x-1">
                <Star className="h-3 w-3 fill-current text-yellow-500" />
                <span>{pkg.rating.toFixed(1)}</span>
              </div>

              {/* Updated */}
              <div className="flex items-center space-x-1">
                <Calendar className="h-3 w-3" />
                <span>{formatDistanceToNow(pkg.publishDate, { addSuffix: true })}</span>
              </div>
            </div>

            {/* Revit Versions */}
            <div className="flex items-center space-x-1">
              {pkg.revitVersions.slice(0, 3).map((version) => (
                <Badge key={version} variant="outline" className="text-xs">
                  {version}
                </Badge>
              ))}
              {pkg.revitVersions.length > 3 && (
                <Badge variant="outline" className="text-xs">
                  +{pkg.revitVersions.length - 3}
                </Badge>
              )}
            </div>
          </div>

          {/* Featured package additional info */}
          {featured && !compact && (
            <div className="pt-2 border-t">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <Button variant="ghost" size="sm" className="h-8 px-2">
                    <BookOpen className="h-3 w-3 mr-1" />
                    Docs
                  </Button>
                  
                  <Button variant="ghost" size="sm" className="h-8 px-2">
                    <Code className="h-3 w-3 mr-1" />
                    Source
                  </Button>
                  
                  <Button variant="ghost" size="sm" className="h-8 px-2">
                    <ExternalLink className="h-3 w-3 mr-1" />
                    Demo
                  </Button>
                </div>
                
                <div className="text-xs text-green-600 font-medium">
                  Editor's Choice
                </div>
              </div>
            </div>
          )}
        </div>
      </Link>
    </CardComponent>
  );
}