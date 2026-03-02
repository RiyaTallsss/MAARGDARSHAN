#!/usr/bin/env python3
"""
S3 Integration Test for MAARGDARSHAN
Tests that all data files can be accessed from S3
"""

import boto3
import os
from botocore.exceptions import ClientError

# Configuration
S3_BUCKET = "maargdarshan-data"
AWS_REGION = "us-east-1"

# Expected files in S3
EXPECTED_FILES = {
    "dem/P5_PAN_CD_N30_000_E078_000_DEM_30m.tif": "DEM (Elevation Data)",
    "osm/northern-zone-260121.osm.pbf": "OSM (Road Networks)",
    "rainfall/Rainfall_2016_districtwise.csv": "Rainfall Data",
    "floods/Flood_Affected_Area_Atlas_of_India.pdf": "Flood Hazard Data"
}

def test_s3_connection():
    """Test basic S3 connection"""
    print("=" * 60)
    print("TEST 1: S3 Connection")
    print("=" * 60)
    
    try:
        s3 = boto3.client('s3', region_name=AWS_REGION)
        response = s3.head_bucket(Bucket=S3_BUCKET)
        print(f"✅ Successfully connected to S3 bucket: {S3_BUCKET}")
        return True
    except ClientError as e:
        print(f"❌ Failed to connect to S3 bucket: {e}")
        return False

def test_file_exists():
    """Test that all expected files exist in S3"""
    print("\n" + "=" * 60)
    print("TEST 2: File Existence Check")
    print("=" * 60)
    
    s3 = boto3.client('s3', region_name=AWS_REGION)
    all_exist = True
    
    for s3_key, description in EXPECTED_FILES.items():
        try:
            response = s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
            size_mb = response['ContentLength'] / (1024 * 1024)
            print(f"✅ {description}")
            print(f"   Path: s3://{S3_BUCKET}/{s3_key}")
            print(f"   Size: {size_mb:.2f} MB")
        except ClientError as e:
            print(f"❌ {description} - NOT FOUND")
            print(f"   Expected: s3://{S3_BUCKET}/{s3_key}")
            all_exist = False
    
    return all_exist

def test_file_download():
    """Test downloading a small file from S3"""
    print("\n" + "=" * 60)
    print("TEST 3: File Download Test")
    print("=" * 60)
    
    s3 = boto3.client('s3', region_name=AWS_REGION)
    test_file = "rainfall/Rainfall_2016_districtwise.csv"
    local_path = "/tmp/test_rainfall.csv"
    
    try:
        print(f"Downloading: {test_file}")
        s3.download_file(S3_BUCKET, test_file, local_path)
        
        # Check file size
        file_size = os.path.getsize(local_path)
        print(f"✅ Successfully downloaded to: {local_path}")
        print(f"   File size: {file_size} bytes")
        
        # Read first few lines
        with open(local_path, 'r') as f:
            lines = f.readlines()[:3]
            print(f"   First 3 lines:")
            for line in lines:
                print(f"     {line.strip()}")
        
        # Cleanup
        os.remove(local_path)
        return True
        
    except Exception as e:
        print(f"❌ Failed to download file: {e}")
        return False

def test_s3_urls():
    """Generate S3 URLs for code configuration"""
    print("\n" + "=" * 60)
    print("TEST 4: S3 URLs for Code Configuration")
    print("=" * 60)
    
    print("\nAdd these to your configuration file:")
    print("-" * 60)
    for s3_key, description in EXPECTED_FILES.items():
        url = f"s3://{S3_BUCKET}/{s3_key}"
        print(f"# {description}")
        print(f"{url}")
        print()

def test_boto3_s3fs():
    """Test if s3fs is available for direct S3 file access"""
    print("\n" + "=" * 60)
    print("TEST 5: S3FS Library Check")
    print("=" * 60)
    
    try:
        import s3fs
        fs = s3fs.S3FileSystem(anon=False)
        
        # Test listing files
        files = fs.ls(S3_BUCKET)
        print(f"✅ s3fs is installed and working")
        print(f"   Found {len(files)} items in bucket")
        return True
        
    except ImportError:
        print("⚠️  s3fs not installed (optional)")
        print("   Install with: pip install s3fs")
        print("   This allows direct file access like: s3fs.open('s3://bucket/file')")
        return False
    except Exception as e:
        print(f"⚠️  s3fs error: {e}")
        return False

def test_rasterio_s3():
    """Test if rasterio can read DEM directly from S3"""
    print("\n" + "=" * 60)
    print("TEST 6: Rasterio S3 Integration")
    print("=" * 60)
    
    try:
        import rasterio
        from rasterio.session import AWSSession
        
        dem_path = f"s3://{S3_BUCKET}/dem/P5_PAN_CD_N30_000_E078_000_DEM_30m.tif"
        
        # Create AWS session for rasterio
        aws_session = AWSSession(
            aws_access_key_id=boto3.Session().get_credentials().access_key,
            aws_secret_access_key=boto3.Session().get_credentials().secret_key,
            region_name=AWS_REGION
        )
        
        with rasterio.Env(aws_session):
            with rasterio.open(dem_path) as src:
                print(f"✅ Rasterio can read DEM from S3")
                print(f"   Shape: {src.shape}")
                print(f"   CRS: {src.crs}")
                print(f"   Bounds: {src.bounds}")
                return True
                
    except ImportError:
        print("⚠️  rasterio not installed")
        print("   Install with: pip install rasterio")
        return False
    except Exception as e:
        print(f"❌ Rasterio S3 read failed: {e}")
        print("   Note: You may need to download DEM locally for processing")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("MAARGDARSHAN - S3 Integration Test Suite")
    print("=" * 60)
    
    results = {
        "S3 Connection": test_s3_connection(),
        "File Existence": test_file_exists(),
        "File Download": test_file_download(),
        "S3FS Library": test_boto3_s3fs(),
        "Rasterio S3": test_rasterio_s3()
    }
    
    # Generate URLs regardless of test results
    test_s3_urls()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    passed_count = sum(results.values())
    total_count = len(results)
    
    print("\n" + "=" * 60)
    print(f"Results: {passed_count}/{total_count} tests passed")
    print("=" * 60)
    
    if results["S3 Connection"] and results["File Existence"] and results["File Download"]:
        print("\n✅ CORE TESTS PASSED - Ready for deployment!")
        print("\nNext steps:")
        print("1. Update your code configuration with S3 URLs above")
        print("2. Test your application locally with S3 data")
        print("3. Deploy backend to AWS Lambda")
        print("4. Deploy frontend to S3 static website")
    else:
        print("\n❌ CORE TESTS FAILED - Fix issues before deployment")
        print("\nTroubleshooting:")
        print("1. Check AWS credentials: aws sts get-caller-identity")
        print("2. Verify bucket exists: aws s3 ls s3://maargdarshan-data/")
        print("3. Check IAM permissions for S3 access")

if __name__ == "__main__":
    main()
